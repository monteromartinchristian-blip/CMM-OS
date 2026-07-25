"""Phase 8.11 – Contradiction Resolution Policy Engine.

Evaluates contradiction resolution proposals against conservative cognitive policy rules
before any future execution.
"""

from __future__ import annotations

from typing import Any

from cmm.cognitive.errors import ResolutionPolicyConflictError
from cmm.cognitive.resolution_contracts import (
    ContradictionResolutionProposal,
    ResolutionDecision,
)
from cmm.cognitive.resolution_policy_contracts import (
    PolicyDecision,
    PolicySeverity,
    ResolutionPolicyEvaluation,
)


class ContradictionResolutionPolicyEngine:
    """Engine that evaluates contradiction resolution proposals against cognitive policies.

    Enforces conservative epistemic governance: preserving uncertainty, requiring human review
    for destructive or subjective changes, and permitting automatic resolution only under strict,
    opt-in criteria.
    """

    def __init__(
        self,
        *,
        allow_auto_resolution: bool = False,
    ) -> None:
        self._allow_auto_resolution = bool(allow_auto_resolution)

    @property
    def allow_auto_resolution(self) -> bool:
        """Return whether automatic resolution is enabled."""
        return self._allow_auto_resolution

    def evaluate(
        self,
        proposal: ContradictionResolutionProposal,
    ) -> ResolutionPolicyEvaluation:
        """Evaluate a ContradictionResolutionProposal deterministically against policy rules.

        Args:
            proposal: The resolution proposal to evaluate.

        Returns:
            A frozen ResolutionPolicyEvaluation record containing the policy decision.

        Raises:
            ResolutionPolicyConflictError: If the proposal input is invalid.
        """
        if not isinstance(proposal, ContradictionResolutionProposal):
            raise ResolutionPolicyConflictError(
                "proposal must be an instance of ContradictionResolutionProposal"
            )

        decision: PolicyDecision
        severity: PolicySeverity
        allowed: bool
        reasons: tuple[str, ...]
        warnings: tuple[str, ...] = ()

        if proposal.decision == ResolutionDecision.REQUEST_HUMAN_REVIEW:
            decision = PolicyDecision.HUMAN_REVIEW_REQUIRED
            severity = PolicySeverity.HIGH
            allowed = False
            reasons = ("Proposal explicitly requires human validation",)

        elif proposal.decision == ResolutionDecision.KEEP_BOTH:
            if self._allow_auto_resolution:
                decision = PolicyDecision.AUTO_APPROVED
                severity = PolicySeverity.LOW
                allowed = True
                reasons = (
                    "Preserving both conflicting knowledge items is safe and auto-approved",
                )
            else:
                decision = PolicyDecision.HUMAN_REVIEW_REQUIRED
                severity = PolicySeverity.LOW
                allowed = False
                reasons = ("Auto resolution is disabled by policy",)

        elif proposal.decision in (
            ResolutionDecision.PREFER_ITEM_A,
            ResolutionDecision.PREFER_ITEM_B,
        ):
            decision = PolicyDecision.HUMAN_REVIEW_REQUIRED
            severity = PolicySeverity.HIGH
            allowed = False
            reasons = (
                "Automatic preference between conflicting knowledge items is forbidden without authority policy",
            )

        elif proposal.decision == ResolutionDecision.MERGE_INFORMATION:
            if self._allow_auto_resolution and proposal.confidence >= 0.90:
                decision = PolicyDecision.AUTO_APPROVED
                severity = PolicySeverity.LOW
                allowed = True
                reasons = (
                    "Information merge approved automatically due to high confidence and policy settings",
                )
            else:
                decision = PolicyDecision.HUMAN_REVIEW_REQUIRED
                severity = PolicySeverity.MEDIUM
                allowed = False
                reasons = (
                    "Information merge requires human review (confidence below 0.90 threshold or auto-resolution disabled)",
                )

        elif proposal.decision == ResolutionDecision.MARK_ONE_INVALID:
            decision = PolicyDecision.HUMAN_REVIEW_REQUIRED
            severity = PolicySeverity.HIGH
            allowed = False
            reasons = ("Changing epistemological validity requires human authority",)

        elif proposal.decision == ResolutionDecision.DEFER:
            decision = PolicyDecision.DEFERRED
            severity = PolicySeverity.MEDIUM
            allowed = False
            reasons = ("Proposal status is deferred due to insufficient information",)

        else:
            raise ResolutionPolicyConflictError(
                f"Unhandled ResolutionDecision: {proposal.decision}"
            )

        meta: dict[str, Any] = {
            "allow_auto_resolution": self._allow_auto_resolution,
            "proposal_decision": proposal.decision.value,
        }

        return ResolutionPolicyEvaluation(
            proposal_id=proposal.id,
            decision=decision,
            severity=severity,
            confidence=proposal.confidence,
            allowed=allowed,
            reasons=reasons,
            warnings=warnings,
            metadata=meta,
        )
