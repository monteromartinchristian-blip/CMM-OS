"""Phase 9.10 – Human Approval System Service.

Central domain manager for creating, deciding, resolving, superseding, and expiring
human approval requests within the Autonomous Agent Runtime.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from .approval_contracts import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalResolution,
)
from .approval_repository import ApprovalRepository, InMemoryApprovalRepository
from .enums import (
    ApprovalDecisionType,
    ApprovalRequestStatus,
)
from .errors import (
    ApprovalActorNotAuthorizedError,
    ApprovalAlreadyResolvedError,
    ApprovalDecisionNotFoundError,
    ApprovalExpiredError,
    ApprovalSupersessionError,
    InvalidApprovalContractError,
)


def _now_utc() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ApprovalService:
    """Core domain service for managing human approval requests, decisions, and resolutions."""

    def __init__(self, repository: ApprovalRepository | None = None) -> None:
        self._repo: ApprovalRepository = repository or InMemoryApprovalRepository()

    @property
    def repository(self) -> ApprovalRepository:
        """Return the underlying ApprovalRepository."""
        return self._repo

    def create_request_from_requirement(
        self,
        requirement: ApprovalRequirement,
        requested_by: str = "agent-runtime",
        supersedes_request_id: str | None = None,
        metadata_override: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create an ApprovalRequest from an ApprovalRequirement specification."""
        if not isinstance(requirement, ApprovalRequirement):
            raise InvalidApprovalContractError(
                f"requirement must be an ApprovalRequirement, got {type(requirement).__name__}"
            )

        request_id = f"approval-req-{uuid.uuid4().hex[:12]}"
        now = _now_utc()

        merged_meta = dict(requirement.metadata)
        if metadata_override:
            merged_meta.update(metadata_override)

        request = ApprovalRequest(
            id=request_id,
            title=requirement.title,
            description=requirement.description,
            requested_by=requested_by,
            agent_run_id=requirement.agent_run_id,
            goal_id=requirement.goal_id,
            workflow_id=requirement.workflow_id,
            operation_id=requirement.operation_id,
            reason_codes=requirement.reason_codes,
            risk_level=requirement.risk_level,
            expected_effects=requirement.expected_effects,
            possible_side_effects=requirement.possible_side_effects,
            rollback_available=requirement.rollback_available,
            rollback_description=requirement.rollback_description,
            required_approvers=requirement.required_approvers,
            minimum_approvals=requirement.minimum_approvals,
            expires_at=requirement.expires_at,
            status=ApprovalRequestStatus.PENDING,
            supersedes_request_id=supersedes_request_id,
            created_at=now,
            updated_at=now,
            metadata=MappingProxyType(dict(merged_meta)),
        )

        return self._repo.add_request(request)

    def create_request(
        self,
        title: str,
        description: str,
        requested_by: str = "agent-runtime",
        agent_run_id: str | None = None,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        operation_id: str | None = None,
        reason_codes: tuple[str, ...] = (),
        risk_level: Any = "medium",
        expected_effects: tuple[str, ...] = (),
        possible_side_effects: tuple[str, ...] = (),
        rollback_available: bool = False,
        rollback_description: str | None = None,
        required_approvers: tuple[str, ...] = (),
        minimum_approvals: int = 1,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create and store a new ApprovalRequest directly."""
        request_id = f"approval-req-{uuid.uuid4().hex[:12]}"
        now = _now_utc()

        request = ApprovalRequest(
            id=request_id,
            title=title,
            description=description,
            requested_by=requested_by,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            workflow_id=workflow_id,
            operation_id=operation_id,
            reason_codes=reason_codes,
            risk_level=risk_level,
            expected_effects=expected_effects,
            possible_side_effects=possible_side_effects,
            rollback_available=rollback_available,
            rollback_description=rollback_description,
            required_approvers=required_approvers,
            minimum_approvals=minimum_approvals,
            expires_at=expires_at,
            status=ApprovalRequestStatus.PENDING,
            created_at=now,
            updated_at=now,
            metadata=MappingProxyType(dict(metadata or {})),
        )

        return self._repo.add_request(request)

    def submit_decision(
        self,
        decision: ApprovalDecision,
        now: datetime | None = None,
    ) -> ApprovalResolution:
        """Submit a human decision for an approval request and resolve status."""
        if not isinstance(decision, ApprovalDecision):
            raise InvalidApprovalContractError(
                f"decision must be an ApprovalDecision, got {type(decision).__name__}"
            )

        current_time = now or _now_utc()
        request = self._repo.get_request(decision.request_id)

        # 1. Check idempotency: if decision already recorded with exact same ID
        try:
            existing_decision = self._repo.get_decision(decision.id)
            if existing_decision == decision:
                existing_resolution = self._repo.get_resolution(request.id)
                if existing_resolution is not None:
                    return existing_resolution
        except ApprovalDecisionNotFoundError:
            pass

        # 2. Check expiration (by timestamp or already marked status)
        if request.status == ApprovalRequestStatus.EXPIRED:
            raise ApprovalExpiredError(
                f"Cannot submit decision: ApprovalRequest {request.id!r} is expired"
            )
        if request.expires_at is not None and request.expires_at <= current_time:
            self._expire_request_internal(request, current_time)
            raise ApprovalExpiredError(
                f"Cannot submit decision: ApprovalRequest {request.id!r} expired at {request.expires_at.isoformat()}"
            )

        # 3. Check if request is already in a terminal state
        if request.is_terminal:
            raise ApprovalAlreadyResolvedError(
                f"Cannot submit decision on request {request.id!r} in terminal status {request.status.value!r}"
            )

        # 4. Check actor authorization
        if (
            request.required_approvers
            and decision.actor_id not in request.required_approvers
        ):
            raise ApprovalActorNotAuthorizedError(
                f"Actor {decision.actor_id!r} is not in required_approvers {request.required_approvers}"
            )

        # Check deduplication per actor
        existing_decisions = self._repo.list_decisions(request.id)
        for prev_dec in existing_decisions:
            if prev_dec.actor_id == decision.actor_id and prev_dec.id != decision.id:
                raise ApprovalActorNotAuthorizedError(
                    f"Actor {decision.actor_id!r} has already submitted a decision for request {request.id!r}"
                )

        # 5. Record the decision
        self._repo.add_decision(decision)

        # 6. Re-evaluate and resolve request state
        return self.resolve(request.id, now=current_time)

    def approve(
        self,
        request_id: str,
        actor_id: str,
        comment: str | None = None,
        conditions: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalResolution:
        """Helper to submit an APPROVE decision."""
        decision = ApprovalDecision(
            id=f"dec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            decision=ApprovalDecisionType.APPROVE,
            actor_id=actor_id,
            conditions=conditions,
            comment=comment,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        return self.submit_decision(decision)

    def approve_with_changes(
        self,
        request_id: str,
        actor_id: str,
        modified_parameters: dict[str, Any],
        comment: str | None = None,
        conditions: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalResolution:
        """Helper to submit an APPROVE_WITH_CHANGES decision."""
        decision = ApprovalDecision(
            id=f"dec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            decision=ApprovalDecisionType.APPROVE_WITH_CHANGES,
            actor_id=actor_id,
            modified_parameters=MappingProxyType(dict(modified_parameters)),
            conditions=conditions,
            comment=comment,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        return self.submit_decision(decision)

    def reject(
        self,
        request_id: str,
        actor_id: str,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalResolution:
        """Helper to submit a REJECT decision."""
        decision = ApprovalDecision(
            id=f"dec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            decision=ApprovalDecisionType.REJECT,
            actor_id=actor_id,
            comment=comment,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        return self.submit_decision(decision)

    def postpone(
        self,
        request_id: str,
        actor_id: str,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalResolution:
        """Helper to submit a POSTPONE decision."""
        decision = ApprovalDecision(
            id=f"dec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            decision=ApprovalDecisionType.POSTPONE,
            actor_id=actor_id,
            comment=comment,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        return self.submit_decision(decision)

    def cancel(
        self,
        request_id: str,
        actor_id: str,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalResolution:
        """Helper to submit a CANCEL decision."""
        decision = ApprovalDecision(
            id=f"dec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            decision=ApprovalDecisionType.CANCEL,
            actor_id=actor_id,
            comment=comment,
            metadata=MappingProxyType(dict(metadata or {})),
        )
        return self.submit_decision(decision)

    def resolve(
        self, request_id: str, now: datetime | None = None
    ) -> ApprovalResolution:
        """Evaluate recorded decisions and resolve effective approval state for a request."""
        request = self._repo.get_request(request_id)
        current_time = now or _now_utc()

        # Check expiration first
        if (
            request.status
            in (ApprovalRequestStatus.PENDING, ApprovalRequestStatus.POSTPONED)
            and request.expires_at is not None
            and request.expires_at <= current_time
        ):
            return self._expire_request_internal(request, current_time)

        decisions = self._repo.list_decisions(request_id)

        # Aggregate decision types and actors
        approvals: list[ApprovalDecision] = []
        approvals_with_changes: list[ApprovalDecision] = []
        rejections: list[ApprovalDecision] = []
        postponements: list[ApprovalDecision] = []
        cancellations: list[ApprovalDecision] = []

        all_conditions: list[str] = []
        approved_params: dict[str, Any] = {}

        for dec in decisions:
            if dec.conditions:
                all_conditions.extend(dec.conditions)

            if dec.decision == ApprovalDecisionType.REJECT:
                rejections.append(dec)
            elif dec.decision == ApprovalDecisionType.CANCEL:
                cancellations.append(dec)
            elif dec.decision == ApprovalDecisionType.POSTPONE:
                postponements.append(dec)
            elif dec.decision == ApprovalDecisionType.APPROVE_WITH_CHANGES:
                approvals_with_changes.append(dec)
                approved_params.update(dec.modified_parameters)
            elif dec.decision == ApprovalDecisionType.APPROVE:
                approvals.append(dec)

        reason_codes: list[str] = list(request.reason_codes)

        # Precedence Rule 1: ANY rejection prevails
        if rejections:
            new_status = ApprovalRequestStatus.REJECTED
            satisfied = False
            may_exec = False
            reason_codes.append("approval.rejected")
        # Precedence Rule 2: ANY cancellation prevails
        elif cancellations:
            new_status = ApprovalRequestStatus.CANCELLED
            satisfied = False
            may_exec = False
            reason_codes.append("approval.cancelled")
        else:
            total_approving_actors = len(
                {d.actor_id for d in approvals + approvals_with_changes}
            )
            if total_approving_actors >= request.minimum_approvals:
                if approvals_with_changes:
                    new_status = ApprovalRequestStatus.APPROVED_WITH_CHANGES
                    satisfied = True
                    # Approval with changes requires re-evaluation / re-validation before execution!
                    may_exec = False
                    reason_codes.append("approval.approved_with_changes")
                else:
                    new_status = ApprovalRequestStatus.APPROVED
                    satisfied = True
                    may_exec = True
                    reason_codes.append("approval.approved")
            elif postponements:
                new_status = ApprovalRequestStatus.POSTPONED
                satisfied = False
                may_exec = False
                reason_codes.append("approval.postponed")
            else:
                new_status = ApprovalRequestStatus.PENDING
                satisfied = False
                may_exec = False
                reason_codes.append("approval.pending_approvals")

        # Update request status in repository if status changed or resolution updated
        if request.status != new_status:
            updated_req = ApprovalRequest.from_mapping(
                {
                    **request.to_dict(),
                    "status": new_status.value,
                    "updated_at": current_time.isoformat(),
                }
            )
            self._repo.update_request(updated_req)

        # Determine obligations for approval with changes
        is_app_changes = new_status == ApprovalRequestStatus.APPROVED_WITH_CHANGES

        resolution = ApprovalResolution(
            request_id=request_id,
            status=new_status,
            satisfied=satisfied,
            may_execute=may_exec,
            approval_count=len(approvals) + len(approvals_with_changes),
            rejection_count=len(rejections),
            required_approval_count=request.minimum_approvals,
            approved_parameters=MappingProxyType(
                dict(approved_params) if is_app_changes else {}
            ),
            conditions=tuple(all_conditions),
            reason_codes=tuple(sorted(set(reason_codes))),
            requires_policy_reevaluation=is_app_changes,
            requires_validation=is_app_changes,
            requires_budget_recalculation=is_app_changes,
            requires_plan_update=is_app_changes,
            resolved_at=current_time,
            metadata=MappingProxyType({"risk_level": request.risk_level.value}),
        )

        return self._repo.resolve_request(resolution)

    def is_approval_satisfied(self, request_id: str) -> bool:
        """Determine if an approval request is satisfied."""
        resolution = self._repo.get_resolution(request_id)
        if resolution is None:
            resolution = self.resolve(request_id)
        return resolution.satisfied

    def may_execute(self, request_id: str) -> bool:
        """Determine if an action associated with an approval request may execute."""
        resolution = self._repo.get_resolution(request_id)
        if resolution is None:
            resolution = self.resolve(request_id)
        return resolution.may_execute

    def supersede(
        self,
        old_request_id: str,
        new_request: ApprovalRequest | ApprovalRequirement,
    ) -> ApprovalRequest:
        """Supersede an active approval request with a new request."""
        old_req = self._repo.get_request(old_request_id)
        if old_req.is_terminal:
            raise ApprovalSupersessionError(
                f"Cannot supersede request {old_request_id!r} in terminal status {old_req.status.value!r}"
            )

        now = _now_utc()

        # Create or update new request
        if isinstance(new_request, ApprovalRequirement):
            created_new = self.create_request_from_requirement(
                new_request,
                supersedes_request_id=old_request_id,
            )

        elif isinstance(new_request, ApprovalRequest):
            created_new = ApprovalRequest.from_mapping(
                {
                    **new_request.to_dict(),
                    "supersedes_request_id": old_request_id,
                    "updated_at": now.isoformat(),
                }
            )
            self._repo.add_request(created_new)
        else:
            raise InvalidApprovalContractError(
                f"new_request must be an ApprovalRequest or ApprovalRequirement, got {type(new_request).__name__}"
            )

        # Mark old request as SUPERSEDED
        updated_old = ApprovalRequest.from_mapping(
            {
                **old_req.to_dict(),
                "status": ApprovalRequestStatus.SUPERSEDED.value,
                "superseded_by_request_id": created_new.id,
                "updated_at": now.isoformat(),
            }
        )
        self._repo.update_request(updated_old)

        # Record resolution for old request
        old_resolution = ApprovalResolution(
            request_id=old_request_id,
            status=ApprovalRequestStatus.SUPERSEDED,
            satisfied=False,
            may_execute=False,
            reason_codes=("approval.superseded",),
            resolved_at=now,
            metadata=MappingProxyType({"superseded_by": created_new.id}),
        )
        self._repo.resolve_request(old_resolution)

        return created_new

    def expire_due_requests(
        self, now: datetime | None = None
    ) -> tuple[ApprovalRequest, ...]:
        """Expire all due requests and generate EXPIRED resolutions."""
        current_time = now or _now_utc()
        expired_list = self._repo.expire_requests(now=current_time)

        for req in expired_list:
            resolution = ApprovalResolution(
                request_id=req.id,
                status=ApprovalRequestStatus.EXPIRED,
                satisfied=False,
                may_execute=False,
                reason_codes=("approval.expired",),
                resolved_at=current_time,
            )
            self._repo.resolve_request(resolution)

        return expired_list

    def _expire_request_internal(
        self, request: ApprovalRequest, current_time: datetime
    ) -> ApprovalResolution:
        """Internal helper to mark a request expired and store resolution."""
        updated_req = ApprovalRequest.from_mapping(
            {
                **request.to_dict(),
                "status": ApprovalRequestStatus.EXPIRED.value,
                "updated_at": current_time.isoformat(),
            }
        )
        self._repo.update_request(updated_req)

        resolution = ApprovalResolution(
            request_id=request.id,
            status=ApprovalRequestStatus.EXPIRED,
            satisfied=False,
            may_execute=False,
            reason_codes=("approval.expired",),
            resolved_at=current_time,
        )
        return self._repo.resolve_request(resolution)
