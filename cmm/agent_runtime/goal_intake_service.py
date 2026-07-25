"""Phase 9.3 – Goal Intake Service and Normalizer.

Provides the normalizer protocol, deterministic normalizer implementation,
and GoalIntakeService orchestrating request normalization, decision-making,
proposal persistence, duplicate detection, and Goal conversion.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cmm.agent_runtime.enums import (
    GoalAmbiguityKind,
    GoalIntakeDecisionType,
    GoalKind,
    GoalProposalStatus,
    GoalSource,
    GoalStatus,
)
from cmm.agent_runtime.errors import (
    GoalNormalizationError,
    GoalProposalConversionError,
    GoalProposalNotFoundError,
    GoalProposalStateError,
)
from cmm.agent_runtime.goal_contracts import (
    Goal,
    GoalPriority,
    GoalQuery,
)
from cmm.agent_runtime.goal_intake_contracts import (
    GoalAmbiguity,
    GoalInformationGap,
    GoalIntakeDecision,
    GoalNormalizationRequest,
    GoalNormalizationResult,
    GoalProposal,
)
from cmm.agent_runtime.goal_intake_repository import (
    GoalProposalRepository,
    InMemoryGoalProposalRepository,
)
from cmm.agent_runtime.goal_manager import (
    TERMINAL_GOAL_STATUSES,
    GoalManager,
)


@runtime_checkable
class GoalNormalizer(Protocol):
    """Protocol for normalizing raw objectives into structured GoalProposals."""

    def normalize(self, request: GoalNormalizationRequest) -> GoalNormalizationResult:
        """Normalize a GoalNormalizationRequest into a GoalNormalizationResult."""
        ...


class DeterministicGoalNormalizer:
    """Pure, deterministic implementation of GoalNormalizer.

    Transforms raw text and structured hints into a GoalProposal without invoking
    external LLM models or non-deterministic systems.
    """

    AMBIGUOUS_KEYWORDS: tuple[str, ...] = (
        "something",
        "stuff",
        "do whatever",
        "fix it",
        "clean up everything",
        "some changes",
        "etc",
    )

    def normalize(self, request: GoalNormalizationRequest) -> GoalNormalizationResult:
        """Normalize request into structured proposal and normalization result."""
        if not isinstance(request, GoalNormalizationRequest):
            raise GoalNormalizationError(
                "request must be a GoalNormalizationRequest instance"
            )

        raw_obj = request.raw_objective.strip()
        if not raw_obj:
            raise GoalNormalizationError("raw_objective cannot be empty or whitespace")

        proposal_id = f"proposal-{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc)

        # 1. Parse Title & Description
        lines = [line.strip() for line in raw_obj.splitlines() if line.strip()]
        title = lines[0] if lines else raw_obj
        if len(title) > 100:
            title = title[:97] + "..."
        description = raw_obj

        # 2. Determine Kind
        kind = GoalKind.TRANSFORMATION
        if request.kind_hint is not None:
            kind = (
                request.kind_hint
                if isinstance(request.kind_hint, GoalKind)
                else GoalKind(request.kind_hint)
            )
        elif (
            request.source == GoalSource.RECURRING_GOAL
            or "recurring" in raw_obj.lower()
        ):
            kind = GoalKind.RECURRING
        elif (
            "fix" in raw_obj.lower()
            or "bug" in raw_obj.lower()
            or "error" in raw_obj.lower()
        ):
            kind = GoalKind.REMEDIATION
        elif "analyze" in raw_obj.lower() or "investigate" in raw_obj.lower():
            kind = GoalKind.ANALYSIS
        elif "test" in raw_obj.lower() or "validate" in raw_obj.lower():
            kind = GoalKind.VALIDATION

        # 3. Determine Priority
        priority: GoalPriority
        if isinstance(request.explicit_priority, GoalPriority):
            priority = request.explicit_priority
        elif isinstance(request.explicit_priority, (int, float)):
            val = float(request.explicit_priority)
            priority = GoalPriority(score=val, user_priority=val)
        else:
            priority = GoalPriority()

        # 4. Check Deadline (No invented deadline)
        deadline = request.explicit_deadline

        # 5. Check Ambiguities & Information Gaps
        ambiguities: list[GoalAmbiguity] = []
        gaps: list[GoalInformationGap] = []
        requires_confirmation = False
        confidence = 1.0
        status = GoalProposalStatus.READY

        # Detect vague / short / ambiguous input
        raw_lower = raw_obj.lower()
        is_ambiguous = len(raw_obj) < 8 or any(
            kw in raw_lower for kw in self.AMBIGUOUS_KEYWORDS
        )

        if is_ambiguous:
            ambiguity_id = f"ambiguity-{uuid.uuid4().hex[:8]}"
            gap_id = f"gap-{uuid.uuid4().hex[:8]}"
            ambiguities.append(
                GoalAmbiguity(
                    id=ambiguity_id,
                    kind=GoalAmbiguityKind.OBJECTIVE,
                    description=f"Raw objective '{raw_obj}' is ambiguous or under-specified.",
                    field_name="raw_objective",
                    blocking=True,
                    suggested_resolution="Provide a detailed, specific objective statement.",
                )
            )
            gaps.append(
                GoalInformationGap(
                    id=gap_id,
                    question="What specific outcome or scope is expected for this goal?",
                    topic="scope_clarification",
                    impact="prevents execution of ambiguous actions",
                    required=True,
                )
            )
            requires_confirmation = True
            confidence = 0.5
            status = GoalProposalStatus.REQUIRES_CLARIFICATION

        # Build parent goal metadata if present
        meta_dict = dict(request.metadata)
        if request.parent_goal_id:
            meta_dict["parent_goal_id"] = request.parent_goal_id

        # Construct GoalProposal
        proposal = GoalProposal(
            id=proposal_id,
            source=request.source,
            raw_objective=raw_obj,
            normalized_title=title,
            normalized_description=description,
            proposed_kind=kind,
            proposed_priority=priority,
            proposed_success_criteria=(),
            proposed_constraints=request.constraints,
            proposed_deadline=deadline,
            proposed_owner_actor_id=request.actor_id,
            proposed_autonomy_level=request.requested_autonomy_level,
            proposed_sensitivity=request.sensitivity,
            proposed_permissions=request.permissions,
            proposed_dependencies=(),
            ambiguities=tuple(ambiguities),
            information_gaps=tuple(gaps),
            requires_confirmation=requires_confirmation,
            confidence=confidence,
            status=status,
            created_at=created_at,
            metadata=meta_dict,
        )

        decisions = [
            GoalIntakeDecision(
                decision_type=(
                    GoalIntakeDecisionType.REQUEST_CLARIFICATION
                    if status == GoalProposalStatus.REQUIRES_CLARIFICATION
                    else GoalIntakeDecisionType.CREATE_PROPOSED_GOAL
                ),
                reason=(
                    "Ambiguity detected; clarification required."
                    if status == GoalProposalStatus.REQUIRES_CLARIFICATION
                    else "Deterministic normalization completed successfully."
                ),
                target_proposal_id=proposal_id,
                created_at=created_at,
            )
        ]

        return GoalNormalizationResult(
            proposal=proposal,
            status=status,
            decisions=tuple(decisions),
            warnings=()
            if status == GoalProposalStatus.READY
            else ("Proposal contains unresolved ambiguities.",),
            errors=(),
            confidence=confidence,
            metadata=meta_dict,
        )


class GoalIntakeService:
    """Service orchestrating goal intake, normalization, proposal state machine,

    duplicate checking, and goal registration via GoalManager.
    """

    def __init__(
        self,
        normalizer: GoalNormalizer | None = None,
        proposal_repo: GoalProposalRepository | None = None,
        goal_manager: GoalManager | None = None,
    ) -> None:
        self._normalizer: GoalNormalizer = (
            normalizer if normalizer is not None else DeterministicGoalNormalizer()
        )
        self._proposal_repo: GoalProposalRepository = (
            proposal_repo
            if proposal_repo is not None
            else InMemoryGoalProposalRepository()
        )
        self._goal_manager: GoalManager | None = goal_manager

    @property
    def proposal_repository(self) -> GoalProposalRepository:
        """Return the underlying GoalProposalRepository."""
        return self._proposal_repo

    @property
    def goal_manager(self) -> GoalManager | None:
        """Return the attached GoalManager, if any."""
        return self._goal_manager

    def process_request(
        self, request: GoalNormalizationRequest
    ) -> GoalNormalizationResult:
        """Process an incoming GoalNormalizationRequest.

        Normalizes the request, performs simple duplicate checks if GoalManager is attached,
        persists the proposal in the repository, and returns the result.
        """
        if not isinstance(request, GoalNormalizationRequest):
            raise GoalNormalizationError(
                "request must be a GoalNormalizationRequest instance"
            )

        result = self._normalizer.normalize(request)
        proposal = result.proposal

        # Duplicate detection check via GoalManager if attached
        candidate_ids: list[str] = []
        if self._goal_manager is not None:
            # Query non-terminal goals
            search_res = self._goal_manager.search_goals(GoalQuery())
            for existing in search_res.goals:
                if existing.status in TERMINAL_GOAL_STATUSES:
                    continue
                # Compare title (case-insensitive), kind, owner, parent_goal_id
                if (
                    existing.title.strip().lower()
                    == proposal.normalized_title.strip().lower()
                    and existing.kind == proposal.proposed_kind
                    and existing.owner_actor_id == proposal.proposed_owner_actor_id
                    and existing.parent_goal_id
                    == proposal.metadata.get("parent_goal_id")
                ):
                    candidate_ids.append(existing.id)

        if candidate_ids:
            dup_decision = GoalIntakeDecision(
                decision_type=GoalIntakeDecisionType.MERGE_WITH_EXISTING,
                reason=f"Potential duplicate active goals detected: {candidate_ids}",
                target_proposal_id=proposal.id,
                candidate_goal_ids=tuple(candidate_ids),
            )
            # Add duplicate decision, update status to REQUIRES_CLARIFICATION, set requires_confirmation
            updated_decisions = list(result.decisions) + [dup_decision]
            proposal = GoalProposal.from_dict(
                {
                    **proposal.to_dict(),
                    "status": GoalProposalStatus.REQUIRES_CLARIFICATION,
                    "requires_confirmation": True,
                }
            )
            result = GoalNormalizationResult(
                proposal=proposal,
                status=GoalProposalStatus.REQUIRES_CLARIFICATION,
                decisions=tuple(updated_decisions),
                warnings=result.warnings
                + ("Potential duplicate active goals detected.",),
                errors=result.errors,
                confidence=result.confidence,
                metadata=result.metadata,
            )

        self._proposal_repo.add(proposal)
        return result

    def accept_proposal(self, proposal_id: str, actor_id: str = "actor-user") -> Goal:
        """Accept a GoalProposal and convert it into an operational Goal.

        Raises:
            GoalProposalNotFoundError: If proposal_id does not exist.
            GoalProposalStateError: If proposal is already accepted, rejected, failed,
                or has blocking ambiguities.
        """
        proposal = self._proposal_repo.get(proposal_id)
        if proposal is None:
            raise GoalProposalNotFoundError(
                f"GoalProposal with ID {proposal_id!r} not found."
            )

        if proposal.status == GoalProposalStatus.ACCEPTED:
            raise GoalProposalStateError(
                f"Proposal {proposal_id!r} has already been accepted."
            )
        if proposal.status == GoalProposalStatus.REJECTED:
            raise GoalProposalStateError(
                f"Cannot accept proposal {proposal_id!r} because it was rejected."
            )
        if proposal.status in (GoalProposalStatus.FAILED, GoalProposalStatus.EXPIRED):
            raise GoalProposalStateError(
                f"Cannot accept proposal {proposal_id!r} in terminal/invalid status {proposal.status!r}."
            )

        # Check for blocking ambiguities
        blocking = [amb for amb in proposal.ambiguities if amb.blocking]
        if blocking and proposal.status == GoalProposalStatus.REQUIRES_CLARIFICATION:
            raise GoalProposalStateError(
                f"Cannot accept proposal {proposal_id!r} while blocking ambiguities remain unresolved."
            )

        # Update proposal status to ACCEPTED
        accepted_proposal = GoalProposal.from_dict(
            {
                **proposal.to_dict(),
                "status": GoalProposalStatus.ACCEPTED,
            }
        )
        self._proposal_repo.update(accepted_proposal)

        # Convert to Goal
        goal = self.convert_proposal_to_goal(accepted_proposal)

        # Register in GoalManager if present
        if self._goal_manager is not None:
            self._goal_manager.register_goal(goal)

        return goal

    def reject_proposal(self, proposal_id: str, reason: str = "") -> GoalProposal:
        """Reject a GoalProposal.

        Raises:
            GoalProposalNotFoundError: If proposal_id does not exist.
            GoalProposalStateError: If proposal has already been accepted.
        """
        proposal = self._proposal_repo.get(proposal_id)
        if proposal is None:
            raise GoalProposalNotFoundError(
                f"GoalProposal with ID {proposal_id!r} not found."
            )

        if proposal.status == GoalProposalStatus.ACCEPTED:
            raise GoalProposalStateError(
                f"Cannot reject proposal {proposal_id!r} because it has already been accepted."
            )

        rejected_proposal = GoalProposal.from_dict(
            {
                **proposal.to_dict(),
                "status": GoalProposalStatus.REJECTED,
            }
        )
        self._proposal_repo.update(rejected_proposal)
        return rejected_proposal

    def request_clarification(self, proposal_id: str, reason: str = "") -> GoalProposal:
        """Request clarification on a GoalProposal.

        Raises:
            GoalProposalNotFoundError: If proposal_id does not exist.
            GoalProposalStateError: If proposal has already been accepted or rejected.
        """
        proposal = self._proposal_repo.get(proposal_id)
        if proposal is None:
            raise GoalProposalNotFoundError(
                f"GoalProposal with ID {proposal_id!r} not found."
            )

        if proposal.status in (
            GoalProposalStatus.ACCEPTED,
            GoalProposalStatus.REJECTED,
        ):
            raise GoalProposalStateError(
                f"Cannot request clarification on proposal {proposal_id!r} in state {proposal.status!r}."
            )

        clarification_proposal = GoalProposal.from_dict(
            {
                **proposal.to_dict(),
                "status": GoalProposalStatus.REQUIRES_CLARIFICATION,
                "requires_confirmation": True,
            }
        )
        self._proposal_repo.update(clarification_proposal)
        return clarification_proposal

    def convert_proposal_to_goal(self, proposal: GoalProposal) -> Goal:
        """Convert a GoalProposal into an operational Goal entity.

        Initial Goal status is always PROPOSED (not active).
        Preserves provenance, criteria, constraints, dependencies, priority, owner,
        sensitivity, permissions, and deadline.

        Raises:
            GoalProposalConversionError: If conversion fails or proposal is invalid.
        """
        if not isinstance(proposal, GoalProposal):
            raise GoalProposalConversionError(
                "proposal must be a GoalProposal instance"
            )

        goal_id = (
            f"goal-{proposal.id}"
            if not proposal.id.startswith("goal-")
            else proposal.id
        )

        priority = (
            proposal.proposed_priority
            if proposal.proposed_priority is not None
            else GoalPriority()
        )

        parent_goal_id = proposal.metadata.get("parent_goal_id")

        meta = dict(proposal.metadata)
        meta["raw_objective"] = proposal.raw_objective
        meta["proposal_id"] = proposal.id

        source_str = (
            proposal.source.value
            if isinstance(proposal.source, GoalSource)
            else str(proposal.source)
        )

        try:
            return Goal(
                id=goal_id,
                title=proposal.normalized_title,
                description=proposal.normalized_description,
                kind=proposal.proposed_kind,
                status=GoalStatus.PROPOSED,  # Invariant #15: not activated automatically
                priority=priority,
                confidence=proposal.confidence,
                success_criteria=proposal.proposed_success_criteria,
                constraints=proposal.proposed_constraints,
                dependencies=proposal.proposed_dependencies,
                parent_goal_id=parent_goal_id,
                source=source_str,
                owner_actor_id=proposal.proposed_owner_actor_id,
                autonomy_level=proposal.proposed_autonomy_level,
                deadline=proposal.proposed_deadline,
                sensitivity=proposal.proposed_sensitivity,
                permissions=proposal.proposed_permissions,
                created_at=proposal.created_at,
                metadata=meta,
            )
        except Exception as exc:
            raise GoalProposalConversionError(
                f"Failed to convert proposal {proposal.id!r} into Goal: {exc}"
            ) from exc
