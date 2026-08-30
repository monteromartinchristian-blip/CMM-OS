"""Phase 10.34 — Domain Session Resumer.

Orchestration of Domain Session resumption over shared Phase 8 session infrastructure.
Treats persisted domain state as untrusted/historical evidence, revalidates current
state fail-closed, re-evaluates permissions and operation availability, and reconstructs
resumed context deterministically without executing operations or mutating memory.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from cmm.domains.enums import DomainStatus
from cmm.domains.errors import (
    DomainSessionResumeError,
    DomainSessionSerializationError,
)
from cmm.domains.session_codec import DomainSessionCodec
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeResult,
    DomainSessionResumeStatus,
    DomainSessionTransition,
)
from cmm.domains.session_revalidation import (
    _extract_slug,
    revalidate_session_state,
)

if TYPE_CHECKING:
    from cmm.domains.event_publisher import DomainKernelEventPublisher
    from cmm.domains.registry import DomainRegistry


class DomainSessionResumer:
    """Orchestrates safe, fail-closed Domain Session resumption."""

    def __init__(
        self,
        registry: DomainRegistry | None = None,
        resolver: Any | None = None,
        composer: Any | None = None,
        fallback_resolver: Callable[[str, tuple[str, ...]], str] | None = None,
        permission_evaluator: (
            Callable[[Any, tuple[str, ...]], tuple[str, ...]] | None
        ) = None,
        operation_filter: (
            Callable[[tuple[str, ...], tuple[str, ...]], tuple[str, ...]] | None
        ) = None,
        workflow_evaluator: Callable[
            [tuple[str, ...]],
            tuple[
                DomainSessionResumeStatus | None,
                tuple[str, ...],
                DomainSessionCheck | None,
            ],
        ]
        | None = None,
        question_evaluator: Callable[
            [tuple[str, ...]],
            tuple[tuple[str, ...], tuple[str, ...]],
        ]
        | None = None,
        approval_evaluator: Callable[
            [tuple[str, ...]],
            tuple[tuple[str, ...], tuple[str, ...]],
        ]
        | None = None,
        next_step_reconstructor: Callable[
            [DomainSessionContext, DomainSessionResumeStatus],
            str | None,
        ]
        | None = None,
        event_publisher: DomainKernelEventPublisher | None = None,
        codec: DomainSessionCodec | None = None,
        persistence_updater: Callable[[DomainSessionContext], None] | None = None,
    ) -> None:
        self._registry = registry
        self._resolver = resolver
        self._composer = composer
        self._fallback_resolver = fallback_resolver
        self._permission_evaluator = permission_evaluator
        self._operation_filter = operation_filter
        self._workflow_evaluator = workflow_evaluator
        self._question_evaluator = question_evaluator
        self._approval_evaluator = approval_evaluator
        self._next_step_reconstructor = next_step_reconstructor
        self._event_publisher = event_publisher
        self._codec = codec or DomainSessionCodec()
        self._persistence_updater = persistence_updater

    def _is_domain_active(self, domain_ref: str) -> bool:
        if self._registry is None:
            return True
        slug = _extract_slug(domain_ref)
        record = self._registry.get_record(slug)
        if record is None:
            return False
        return record.status in (DomainStatus.ACTIVE, DomainStatus.DEGRADED)

    def resume(
        self,
        request: DomainSessionResumeRequest,
        session_context: DomainSessionContext | Mapping[str, Any] | None = None,
    ) -> DomainSessionResumeResult:
        """Attempt to resume a domain session strictly and safely."""
        # 1. Extract context
        context: DomainSessionContext | None = None
        if isinstance(session_context, DomainSessionContext):
            context = session_context
        elif isinstance(session_context, Mapping):
            context = self._codec.extract_from_session(session_context)
            if context is None:
                try:
                    context = DomainSessionContext.from_dict(session_context)
                except Exception as exc:
                    raise DomainSessionSerializationError(
                        f"Failed to parse session context mapping: {exc}",
                        field="session_context",
                    ) from exc
        elif session_context is not None and hasattr(session_context, "metadata"):
            context = self._codec.extract_from_session(session_context)

        if context is None:
            raise DomainSessionResumeError(
                "Cannot resume: session context is missing or cannot be extracted",
                field="session_context",
            )

        session_id = request.session_id or context.session_id
        previous_revision = context.revision
        checks: list[DomainSessionCheck] = []
        warnings: list[str] = []

        # 2. Pure revalidation
        pure_checks = revalidate_session_state(context, self._registry, request)
        checks.extend(pure_checks)

        # 3. Check for blocking / incompatible findings
        blocking_findings = [c.message for c in checks if c.blocking]
        has_incompatible = any(
            c.status is DomainSessionCheckStatus.INCOMPATIBLE for c in checks
        )

        if blocking_findings:
            # Check if primary domain is missing/disabled and we have a fallback resolver
            p_active = self._is_domain_active(context.primary_domain)
            if not p_active and self._fallback_resolver is not None:
                # Attempt safe re-resolution
                try:
                    new_primary = self._fallback_resolver(
                        context.primary_domain, context.supporting_domains
                    )
                except Exception:  # noqa: BLE001
                    new_primary = None

                if new_primary and self._is_domain_active(new_primary):
                    # Filter out primary domain blocking check and proceed to re-resolve
                    blocking_findings = [
                        c.message
                        for c in checks
                        if c.blocking and c.name != "primary_domain_status"
                    ]
                else:
                    status = (
                        DomainSessionResumeStatus.INCOMPATIBLE
                        if has_incompatible
                        else DomainSessionResumeStatus.BLOCKED
                    )
                    return DomainSessionResumeResult(
                        status=status,
                        session_id=session_id,
                        previous_revision=previous_revision,
                        resumed_revision=previous_revision,
                        context=None,
                        checks=tuple(checks),
                        warnings=tuple(warnings),
                        blocking_findings=tuple(blocking_findings),
                        recorded_resumption=False,
                    )
            else:
                status = (
                    DomainSessionResumeStatus.INCOMPATIBLE
                    if has_incompatible
                    else DomainSessionResumeStatus.BLOCKED
                )
                return DomainSessionResumeResult(
                    status=status,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=tuple(blocking_findings),
                    recorded_resumption=False,
                )

        # 4. Domain Resolution / Recomposition logic
        status = DomainSessionResumeStatus.RESUMED
        effective_primary = context.primary_domain
        effective_supporting = context.supporting_domains
        new_transition: DomainSessionTransition | None = None
        now_ts = request.temporal_reference or datetime.now(timezone.utc)

        # Check primary domain
        if not self._is_domain_active(context.primary_domain):
            if self._fallback_resolver is not None:
                effective_primary = self._fallback_resolver(
                    context.primary_domain, context.supporting_domains
                )
                status = DomainSessionResumeStatus.RE_RESOLVED
                new_transition = DomainSessionTransition(
                    previous_primary_domain=context.primary_domain,
                    new_primary_domain=effective_primary,
                    previous_supporting_domains=context.supporting_domains,
                    new_supporting_domains=context.supporting_domains,
                    reason_code="RE_RESOLUTION",
                    occurred_at=now_ts,
                )
            else:
                return DomainSessionResumeResult(
                    status=DomainSessionResumeStatus.BLOCKED,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=(
                        f"Primary domain '{context.primary_domain}' is inactive and no resolver available",
                    ),
                    recorded_resumption=False,
                )

        # Check supporting domains
        active_supporting = tuple(
            sup for sup in effective_supporting if self._is_domain_active(sup)
        )
        if active_supporting != effective_supporting:
            effective_supporting = active_supporting
            if new_transition is None:
                status = DomainSessionResumeStatus.RECOMPOSED
                new_transition = DomainSessionTransition(
                    previous_primary_domain=context.primary_domain,
                    new_primary_domain=effective_primary,
                    previous_supporting_domains=context.supporting_domains,
                    new_supporting_domains=effective_supporting,
                    reason_code="RECOMPOSITION_SUPPORTING_DISABLED",
                    occurred_at=now_ts,
                )

        # 5. Permission re-evaluation
        if self._permission_evaluator is not None:
            effective_permissions = self._permission_evaluator(
                request.actor, context.effective_permission_refs
            )
        else:
            effective_permissions = context.effective_permission_refs

        # 6. Operation recalculation
        if self._operation_filter is not None:
            effective_operations = self._operation_filter(
                effective_permissions, context.available_operation_ids
            )
        else:
            effective_operations = context.available_operation_ids

        # 7. Workflow validation
        effective_workflows = context.active_workflow_refs
        if self._workflow_evaluator is not None:
            wf_status, wf_refs, wf_check = self._workflow_evaluator(
                context.active_workflow_refs
            )
            if wf_check is not None:
                checks.append(wf_check)
            if wf_status is not None:
                if wf_status in (
                    DomainSessionResumeStatus.INCOMPATIBLE,
                    DomainSessionResumeStatus.BLOCKED,
                ):
                    return DomainSessionResumeResult(
                        status=wf_status,
                        session_id=session_id,
                        previous_revision=previous_revision,
                        resumed_revision=previous_revision,
                        context=None,
                        checks=tuple(checks),
                        warnings=tuple(warnings),
                        blocking_findings=(
                            wf_check.message
                            if wf_check
                            else "Workflow validation blocked continuation",
                        ),
                        recorded_resumption=False,
                    )
                if status is DomainSessionResumeStatus.RESUMED:
                    status = wf_status
            effective_workflows = wf_refs

        # 8. Questions and Approvals recovery
        recovered_questions = context.pending_domain_question_refs
        if self._question_evaluator is not None:
            recovered_questions, invalid_questions = self._question_evaluator(
                context.pending_domain_question_refs
            )
            if invalid_questions:
                warnings.append(
                    f"Dropped {len(invalid_questions)} invalidated questions"
                )

        recovered_approvals = context.approval_refs
        if self._approval_evaluator is not None:
            recovered_approvals, expired_approvals = self._approval_evaluator(
                context.approval_refs
            )
            if expired_approvals:
                warnings.append(
                    f"Dropped {len(expired_approvals)} expired/invalid approvals"
                )

        # 9. Next recommended step
        if self._next_step_reconstructor is not None:
            next_step = self._next_step_reconstructor(context, status)
        else:
            next_step = context.next_recommended_step

        # 10. Transitions consolidation
        transitions = (
            context.domain_transitions + (new_transition,)
            if new_transition
            else context.domain_transitions
        )

        resumed_context = DomainSessionContext(
            session_id=session_id,
            primary_domain=effective_primary,
            supporting_domains=effective_supporting,
            domain_versions=context.domain_versions,
            composition_id=context.composition_id,
            effective_profile=context.effective_profile,
            effective_rule_ids=context.effective_rule_ids,
            effective_permission_refs=effective_permissions,
            active_workflow_refs=effective_workflows,
            available_operation_ids=effective_operations,
            domain_resource_refs=context.domain_resource_refs,
            domain_knowledge_refs=context.domain_knowledge_refs,
            pending_domain_question_refs=recovered_questions,
            domain_conflict_refs=context.domain_conflict_refs,
            approval_refs=recovered_approvals,
            partial_result_refs=context.partial_result_refs,
            trace_refs=context.trace_refs,
            domain_transitions=transitions,
            last_resolution_id=context.last_resolution_id,
            next_recommended_step=next_step,
            revision=previous_revision + 1,
            updated_at=now_ts,
            metadata=dict(context.metadata),
        )

        # 11. Persistence boundary execution
        if self._persistence_updater is not None:
            try:
                self._persistence_updater(resumed_context)
            except Exception as exc:  # noqa: BLE001
                return DomainSessionResumeResult(
                    status=DomainSessionResumeStatus.FAILED,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=(f"Persistence failure: {exc}",),
                    recorded_resumption=False,
                )

        return DomainSessionResumeResult(
            status=status,
            session_id=session_id,
            previous_revision=previous_revision,
            resumed_revision=previous_revision + 1,
            context=resumed_context,
            checks=tuple(checks),
            warnings=tuple(warnings),
            blocking_findings=(),
            recovered_question_refs=recovered_questions,
            recovered_approval_refs=recovered_approvals,
            next_recommended_step=next_step,
            recorded_resumption=True,
            metadata=dict(context.metadata),
        )


__all__ = [
    "DomainSessionResumer",
]
