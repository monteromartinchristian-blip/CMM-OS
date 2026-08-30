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

from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainResolutionStatus, DomainStatus
from cmm.domains.errors import (
    DomainSessionResumeError,
    DomainSessionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult
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
        conflict_evaluator: Callable[
            [tuple[str, ...]],
            tuple[DomainSessionResumeStatus | None, tuple[DomainSessionCheck, ...]],
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
        session_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self._registry = registry
        self._resolver = resolver
        self._composer = composer or DefaultDomainComposer()
        self._fallback_resolver = fallback_resolver
        self._permission_evaluator = permission_evaluator
        self._operation_filter = operation_filter
        self._workflow_evaluator = workflow_evaluator
        self._question_evaluator = question_evaluator
        self._approval_evaluator = approval_evaluator
        self._conflict_evaluator = conflict_evaluator
        self._next_step_reconstructor = next_step_reconstructor
        self._event_publisher = event_publisher
        self._codec = codec or DomainSessionCodec()
        self._persistence_updater = persistence_updater
        self._session_loader = session_loader

    def _is_domain_active(self, domain_ref: str) -> bool:
        if self._registry is None:
            return False
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
        shared_session_id: str | None = None
        if isinstance(session_context, DomainSessionContext):
            context = session_context
            shared_session_id = context.session_id
        elif isinstance(session_context, Mapping):
            shared_session_id = session_context.get(
                "session_id"
            ) or session_context.get("id")
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
            shared_session_id = getattr(session_context, "session_id", None) or getattr(
                session_context, "id", None
            )
            context = self._codec.extract_from_session(session_context)
        elif self._session_loader is not None:
            loaded_session = self._session_loader(request.session_id)
            if loaded_session is not None:
                if isinstance(loaded_session, DomainSessionContext):
                    context = loaded_session
                    shared_session_id = context.session_id
                elif isinstance(loaded_session, Mapping):
                    shared_session_id = loaded_session.get(
                        "session_id"
                    ) or loaded_session.get("id")
                    context = self._codec.extract_from_session(loaded_session)
                elif hasattr(loaded_session, "metadata"):
                    shared_session_id = getattr(
                        loaded_session, "session_id", None
                    ) or getattr(loaded_session, "id", None)
                    context = self._codec.extract_from_session(loaded_session)

        if context is None:
            raise DomainSessionResumeError(
                "Cannot resume: session context is missing or cannot be extracted",
                field="session_context",
            )

        # 1.1 Strict Session ID Binding (MAJOR-01)
        if request.session_id != context.session_id:
            raise DomainSessionResumeError(
                f"Session ID mismatch between request ({request.session_id}) and domain session context ({context.session_id})",
                field="session_id",
            )
        if shared_session_id is not None and shared_session_id != request.session_id:
            raise DomainSessionResumeError(
                f"Session ID mismatch between request ({request.session_id}) and shared session envelope ({shared_session_id})",
                field="session_id",
            )

        session_id = request.session_id
        previous_revision = context.revision
        checks: list[DomainSessionCheck] = []
        warnings: list[str] = []

        # 1.2 Mandatory authorities check (BLOCKER-01 & BLOCKER-03)
        if self._registry is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="registry_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message="Domain registry authority is required for resumption",
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    "Domain registry authority is required for resumption",
                ),
                recorded_resumption=False,
            )

        if self._permission_evaluator is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="permission_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message="Permission authority is required for resumption",
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=("Permission authority is required for resumption",),
                recorded_resumption=False,
            )

        if self._operation_filter is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="operation_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message="Operation authority is required for resumption",
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=("Operation authority is required for resumption",),
                recorded_resumption=False,
            )

        if self._persistence_updater is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.FAILED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="persistence_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message="Persistence authority is required for resumption",
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=("Persistence authority is required for resumption",),
                recorded_resumption=False,
            )

        # 2. Pure revalidation
        pure_checks = revalidate_session_state(context, self._registry, request)
        checks.extend(pure_checks)

        # 2.5 Conflict evaluation
        if self._conflict_evaluator is not None:
            conf_status, conf_checks = self._conflict_evaluator(
                context.domain_conflict_refs
            )
            checks.extend(conf_checks)
            if (
                any(c.blocking for c in conf_checks)
                or conf_status is DomainSessionResumeStatus.BLOCKED
            ):
                return DomainSessionResumeResult(
                    status=DomainSessionResumeStatus.BLOCKED,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=tuple(
                        c.message for c in conf_checks if c.blocking
                    )
                    or ("Unresolved blocking conflict in session",),
                    recorded_resumption=False,
                )

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

        # 4.5 Real Composition execution when composition is needed or composer provided (BLOCKER-02)
        composition_id = context.composition_id
        effective_profile = context.effective_profile
        effective_rules = context.effective_rule_ids
        available_ops_from_comp: tuple[str, ...] | None = None
        perms_from_comp: tuple[str, ...] | None = None

        composer_to_use = self._composer
        if composer_to_use is None and (
            status
            in (
                DomainSessionResumeStatus.RECOMPOSED,
                DomainSessionResumeStatus.RE_RESOLVED,
            )
            or context.composition_id is None
        ):
            composer_to_use = DefaultDomainComposer()

        if composer_to_use is not None:
            res_result = DomainResolutionResult(
                id=f"domain-resolution-resume-{session_id}",
                context_id=f"ctx-resume-{session_id}",
                status=DomainResolutionStatus.RESOLVED,
                primary_domain=DomainId(slug=_extract_slug(effective_primary)),
                supporting_domains=tuple(
                    DomainId(slug=_extract_slug(s)) for s in effective_supporting
                ),
                confidence=1.0,
                resolved_at=now_ts,
            )
            definitions: list[DomainDefinition] = []
            if self._registry is not None:
                p_rec = self._registry.get_record(_extract_slug(effective_primary))
                if p_rec is not None:
                    definitions.append(p_rec.definition)
                for s in effective_supporting:
                    s_rec = self._registry.get_record(_extract_slug(s))
                    if s_rec is not None:
                        definitions.append(s_rec.definition)

            try:
                composed = composer_to_use.compose(res_result, definitions)
            except TypeError:
                composed = composer_to_use.compose(res_result)

            if (
                context.composition_id is not None
                and status is DomainSessionResumeStatus.RESUMED
            ):
                composition_id = context.composition_id
            else:
                composition_id = (
                    getattr(composed, "id", None) or f"domain-composition-{session_id}"
                )
            raw_profile = getattr(composed, "effective_profile", None)
            effective_profile = (
                raw_profile
                if (raw_profile is None or isinstance(raw_profile, str))
                else getattr(raw_profile, "name", str(raw_profile))
            )
            raw_rules = getattr(composed, "rules", ())
            if isinstance(raw_rules, (list, tuple, set, frozenset)):
                effective_rules = tuple(
                    str(getattr(r, "identifier", getattr(r, "id", r)))
                    for r in raw_rules
                )
            else:
                effective_rules = ()
            raw_perms = getattr(composed, "permissions", ())
            if hasattr(raw_perms, "granted_permissions"):
                perms_from_comp = tuple(str(p) for p in raw_perms.granted_permissions)
            elif isinstance(raw_perms, (list, tuple, set, frozenset)):
                perms_from_comp = tuple(
                    str(getattr(p, "identifier", getattr(p, "id", p)))
                    for p in raw_perms
                )
            else:
                perms_from_comp = ()

            raw_ops = getattr(composed, "operations", ())
            if isinstance(raw_ops, (list, tuple, set, frozenset)):
                available_ops_from_comp = tuple(
                    str(getattr(o, "identifier", getattr(o, "id", o))) for o in raw_ops
                )
            else:
                available_ops_from_comp = ()

        # 5. Permission re-evaluation (BLOCKER-01)
        perms_input = (
            perms_from_comp
            if perms_from_comp is not None
            else context.effective_permission_refs
        )
        if self._permission_evaluator is not None:
            effective_permissions = self._permission_evaluator(
                request.actor, perms_input
            )
        elif perms_from_comp is not None:
            effective_permissions = perms_from_comp
        else:
            effective_permissions = ()

        # 6. Operation recalculation (BLOCKER-01)
        ops_input = (
            available_ops_from_comp
            if available_ops_from_comp is not None
            else context.available_operation_ids
        )
        if self._operation_filter is not None:
            effective_operations = self._operation_filter(
                effective_permissions, ops_input
            )
        elif available_ops_from_comp is not None:
            effective_operations = available_ops_from_comp
        else:
            effective_operations = ()

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

        if status in (
            DomainSessionResumeStatus.RESUMED,
            DomainSessionResumeStatus.RECOMPOSED,
            DomainSessionResumeStatus.RE_RESOLVED,
        ):
            if recovered_questions:
                status = DomainSessionResumeStatus.WAITING_FOR_USER
            elif recovered_approvals:
                status = DomainSessionResumeStatus.WAITING_FOR_APPROVAL

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
            composition_id=composition_id,
            effective_profile=effective_profile,
            effective_rule_ids=effective_rules,
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

        # 11. Persistence boundary execution (BLOCKER-03: MUST HAPPEN BEFORE EVENT PUBLICATION)
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

        # 12. Event publication boundary (ONLY AFTER SUCCESSFUL PERSISTENCE COMMIT)
        if self._event_publisher is not None:
            from cmm.domains.event_factory import DomainEventFactory

            factory = DomainEventFactory()
            if status is DomainSessionResumeStatus.RE_RESOLVED:
                evt = factory.create_event(
                    event_type="domain.resolution.completed",
                    domain_id=effective_primary,
                    actor=str(request.actor or "system"),
                    session_id=session_id,
                    payload={
                        "previous_primary": context.primary_domain,
                        "new_primary": effective_primary,
                    },
                )
                self._event_publisher.publish(evt)
            elif status is DomainSessionResumeStatus.RECOMPOSED:
                evt = factory.create_event(
                    event_type="domain.composition.updated",
                    domain_id=effective_primary,
                    related_domain_ids=effective_supporting,
                    actor=str(request.actor or "system"),
                    session_id=session_id,
                    payload={
                        "previous_supporting": list(context.supporting_domains),
                        "new_supporting": list(effective_supporting),
                    },
                )
                self._event_publisher.publish(evt)

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
