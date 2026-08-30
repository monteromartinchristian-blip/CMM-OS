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
    DomainError,
    DomainSessionResumeError,
    DomainSessionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
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
    merge_resume_status,
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
        shared_session_adapter: Any | None = None,
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
        self._shared_session_adapter = shared_session_adapter

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

        durable_context: DomainSessionContext | None = None
        if self._shared_session_adapter is not None:
            durable_context = self._shared_session_adapter.load_domain_session(
                request.session_id
            )

        explicit_context: DomainSessionContext | None = None
        if isinstance(session_context, DomainSessionContext):
            explicit_context = session_context
            shared_session_id = explicit_context.session_id
        elif isinstance(session_context, Mapping):
            shared_session_id = session_context.get(
                "session_id"
            ) or session_context.get("id")
            extracted = self._codec.extract_from_session(session_context)
            if extracted is None:
                try:
                    explicit_context = DomainSessionContext.from_dict(session_context)
                except Exception as exc:
                    raise DomainSessionSerializationError(
                        f"Failed to parse session context mapping: {exc}",
                        field="session_context",
                    ) from exc
            else:
                explicit_context = extracted
        elif session_context is not None and hasattr(session_context, "metadata"):
            shared_session_id = getattr(session_context, "session_id", None) or getattr(
                session_context, "id", None
            )
            explicit_context = self._codec.extract_from_session(session_context)
        elif self._session_loader is not None:
            loaded_session = self._session_loader(request.session_id)
            if loaded_session is not None:
                if isinstance(loaded_session, DomainSessionContext):
                    explicit_context = loaded_session
                    shared_session_id = explicit_context.session_id
                elif isinstance(loaded_session, Mapping):
                    shared_session_id = loaded_session.get(
                        "session_id"
                    ) or loaded_session.get("id")
                    explicit_context = self._codec.extract_from_session(loaded_session)
                elif hasattr(loaded_session, "metadata"):
                    shared_session_id = getattr(
                        loaded_session, "session_id", None
                    ) or getattr(loaded_session, "id", None)
                    explicit_context = self._codec.extract_from_session(loaded_session)

        if self._shared_session_adapter is not None:
            if durable_context is not None:
                if explicit_context is not None:
                    if explicit_context.session_id != request.session_id:
                        raise DomainSessionResumeError(
                            f"Session ID mismatch between request ({request.session_id}) and domain session context ({explicit_context.session_id})",
                            field="session_id",
                        )
                    if explicit_context.revision != durable_context.revision:
                        return DomainSessionResumeResult(
                            status=DomainSessionResumeStatus.FAILED,
                            session_id=request.session_id,
                            previous_revision=durable_context.revision,
                            resumed_revision=durable_context.revision,
                            context=None,
                            checks=(
                                DomainSessionCheck(
                                    name="authoritative_revision_check",
                                    status=DomainSessionCheckStatus.BLOCKING,
                                    message=(
                                        f"Explicit session context revision ({explicit_context.revision}) "
                                        f"does not match authoritative durable revision ({durable_context.revision})"
                                    ),
                                    blocking=True,
                                ),
                            ),
                            warnings=(),
                            blocking_findings=(
                                (
                                    f"Explicit session context revision ({explicit_context.revision}) "
                                    f"does not match authoritative durable revision ({durable_context.revision})"
                                ),
                            ),
                            recorded_resumption=False,
                        )
                context = durable_context
                shared_session_id = durable_context.session_id
            else:
                context = explicit_context
                shared_session_id = context.session_id if context else None
        else:
            context = explicit_context

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

        if self._shared_session_adapter is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.FAILED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="shared_persistence_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=(
                            "Shared session persistence authority is required "
                            "for resumption"
                        ),
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    "Shared session persistence authority is required for resumption",
                ),
                recorded_resumption=False,
            )

        if context.active_workflow_refs and self._workflow_evaluator is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="workflow_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=(
                            "Workflow authority is required for resumption when "
                            "active workflows are present"
                        ),
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    (
                        "Workflow authority is required for resumption when active "
                        "workflows are present"
                    ),
                ),
                recorded_resumption=False,
            )

        if context.domain_conflict_refs and self._conflict_evaluator is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="conflict_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=(
                            "Conflict authority is required for resumption when "
                            "conflict references are present"
                        ),
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    (
                        "Conflict authority is required for resumption when "
                        "conflict references are present"
                    ),
                ),
                recorded_resumption=False,
            )

        if context.pending_domain_question_refs and self._question_evaluator is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="question_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=(
                            "Question authority is required for resumption when "
                            "pending questions are present"
                        ),
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    (
                        "Question authority is required for resumption when "
                        "pending questions are present"
                    ),
                ),
                recorded_resumption=False,
            )

        if context.approval_refs and self._approval_evaluator is None:
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.BLOCKED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=(
                    DomainSessionCheck(
                        name="approval_authority_check",
                        status=DomainSessionCheckStatus.BLOCKING,
                        message=(
                            "Approval authority is required for resumption when "
                            "approvals are present"
                        ),
                        blocking=True,
                    ),
                ),
                warnings=(),
                blocking_findings=(
                    (
                        "Approval authority is required for resumption when "
                        "approvals are present"
                    ),
                ),
                recorded_resumption=False,
            )

        # 2. Pure revalidation
        pure_checks = revalidate_session_state(context, self._registry, request)
        checks.extend(pure_checks)

        status: DomainSessionResumeStatus = DomainSessionResumeStatus.RESUMED

        # 2.5 Conflict evaluation
        if self._conflict_evaluator is not None:
            conf_status, conf_checks = self._conflict_evaluator(
                context.domain_conflict_refs
            )
            checks.extend(conf_checks)
            if conf_status is not None:
                status = merge_resume_status(status, conf_status)
            if any(c.blocking for c in conf_checks) or status in (
                DomainSessionResumeStatus.FAILED,
                DomainSessionResumeStatus.BLOCKED,
                DomainSessionResumeStatus.INCOMPATIBLE,
            ):
                return DomainSessionResumeResult(
                    status=status
                    if status
                    in (
                        DomainSessionResumeStatus.FAILED,
                        DomainSessionResumeStatus.BLOCKED,
                        DomainSessionResumeStatus.INCOMPATIBLE,
                    )
                    else DomainSessionResumeStatus.BLOCKED,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=tuple(
                        c.message for c in conf_checks if c.blocking
                    )
                    or (f"Conflict evaluation resulted in {status.value}",),
                    recorded_resumption=False,
                )

        # 3. Check for blocking / incompatible findings
        blocking_findings = [c.message for c in checks if c.blocking]
        has_incompatible = any(
            c.status is DomainSessionCheckStatus.INCOMPATIBLE for c in checks
        )

        re_resolution_result: DomainResolutionResult | None = None
        effective_primary = context.primary_domain
        effective_supporting = context.supporting_domains
        now_ts = request.temporal_reference or datetime.now(timezone.utc)

        if blocking_findings:
            p_active = self._is_domain_active(context.primary_domain)
            if not p_active:
                if self._resolver is not None:
                    all_reg_domains = (
                        tuple(r.definition.id for r in self._registry.list_records())
                        if self._registry is not None
                        else ()
                    )
                    avail_slug_set = {d.slug for d in all_reg_domains}
                    res_ctx = DomainResolutionContext(
                        id=f"domain-resolution-ctx-resume-{session_id}",
                        session_id=session_id,
                        objective=(
                            f"Domain session resumption for session '{session_id}' "
                            f"(re-resolve primary domain '{context.primary_domain}')"
                        ),
                        available_domains=all_reg_domains,
                        explicit_domains=tuple(
                            DomainId(slug=_extract_slug(s))
                            for s in context.supporting_domains
                            if _extract_slug(s) in avail_slug_set
                        ),
                        active_domains=(
                            tuple(
                                r.definition.id
                                for r in self._registry.list_records()
                                if r.status
                                in (DomainStatus.ACTIVE, DomainStatus.DEGRADED)
                            )
                            if self._registry is not None
                            else ()
                        ),
                        current_profile=context.effective_profile,
                        current_workflow=(
                            context.active_workflow_refs[0]
                            if context.active_workflow_refs
                            else None
                        ),
                        requested_operations=context.available_operation_ids,
                        actor=str(request.actor or "system"),
                        temporal_reference=now_ts,
                    )
                    try:
                        resolved_cand = self._resolver.resolve(res_ctx)
                    except DomainError as exc:
                        return DomainSessionResumeResult(
                            status=DomainSessionResumeStatus.BLOCKED,
                            session_id=session_id,
                            previous_revision=previous_revision,
                            resumed_revision=previous_revision,
                            context=None,
                            checks=tuple(checks),
                            warnings=tuple(warnings),
                            blocking_findings=(f"Domain resolution failed: {exc}",),
                            recorded_resumption=False,
                        )

                    if (
                        resolved_cand is None
                        or resolved_cand.status != DomainResolutionStatus.RESOLVED
                        or resolved_cand.primary_domain is None
                    ):
                        res_status_name = (
                            resolved_cand.status.value
                            if resolved_cand and hasattr(resolved_cand, "status")
                            else "UNRESOLVED"
                        )
                        return DomainSessionResumeResult(
                            status=DomainSessionResumeStatus.BLOCKED,
                            session_id=session_id,
                            previous_revision=previous_revision,
                            resumed_revision=previous_revision,
                            context=None,
                            checks=tuple(checks),
                            warnings=tuple(warnings),
                            blocking_findings=(
                                f"Domain resolution for inactive primary domain failed with status '{res_status_name}'",
                            ),
                            recorded_resumption=False,
                        )

                    if (
                        resolved_cand.confidence is not None
                        and resolved_cand.confidence < 0.5
                    ):
                        return DomainSessionResumeResult(
                            status=DomainSessionResumeStatus.BLOCKED,
                            session_id=session_id,
                            previous_revision=previous_revision,
                            resumed_revision=previous_revision,
                            context=None,
                            checks=tuple(checks),
                            warnings=tuple(warnings),
                            blocking_findings=(
                                f"Domain resolution confidence ({resolved_cand.confidence}) is below required threshold",
                            ),
                            recorded_resumption=False,
                        )

                    new_slug = _extract_slug(
                        resolved_cand.primary_domain.slug
                        if hasattr(resolved_cand.primary_domain, "slug")
                        else str(resolved_cand.primary_domain)
                    )
                    if not self._is_domain_active(new_slug):
                        return DomainSessionResumeResult(
                            status=DomainSessionResumeStatus.BLOCKED,
                            session_id=session_id,
                            previous_revision=previous_revision,
                            resumed_revision=previous_revision,
                            context=None,
                            checks=tuple(checks),
                            warnings=tuple(warnings),
                            blocking_findings=(
                                f"Resolved primary domain '{new_slug}' is not active in registry",
                            ),
                            recorded_resumption=False,
                        )

                    re_resolution_result = resolved_cand
                    effective_primary = f"domain:{new_slug}"
                    if resolved_cand.supporting_domains:
                        sup_slugs = tuple(
                            f"domain:{s.slug if hasattr(s, 'slug') else str(s)}"
                            for s in resolved_cand.supporting_domains
                        )
                        effective_supporting = tuple(
                            s for s in sup_slugs if self._is_domain_active(s)
                        )

                    blocking_findings = [
                        c.message
                        for c in checks
                        if c.blocking and c.name != "primary_domain_status"
                    ]
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
                            f"Primary domain '{context.primary_domain}' is inactive and canonical resolver authority is required",
                        ),
                        recorded_resumption=False,
                    )

            if blocking_findings:
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
        new_transition: DomainSessionTransition | None = None
        if re_resolution_result is not None:
            status = merge_resume_status(status, DomainSessionResumeStatus.RE_RESOLVED)
            last_resolution_id = re_resolution_result.id
        else:
            last_resolution_id = context.last_resolution_id

        # Check supporting domains
        active_supporting = tuple(
            sup for sup in effective_supporting if self._is_domain_active(sup)
        )
        if active_supporting != effective_supporting:
            effective_supporting = active_supporting
            if re_resolution_result is None:
                status = merge_resume_status(
                    status, DomainSessionResumeStatus.RECOMPOSED
                )

        # 4.5 Real Composition execution when composition is needed or composer provided
        composition_id = context.composition_id
        effective_profile = context.effective_profile
        effective_rules = context.effective_rule_ids
        available_ops_from_comp: tuple[str, ...] | None = None
        perms_from_comp: tuple[str, ...] | None = None

        composer_to_use = self._composer
        needs_composition = (
            status
            in (
                DomainSessionResumeStatus.RECOMPOSED,
                DomainSessionResumeStatus.RE_RESOLVED,
            )
            or context.composition_id is None
        )
        if composer_to_use is None and needs_composition:
            composer_to_use = DefaultDomainComposer()

        if needs_composition and composer_to_use is not None:
            if re_resolution_result is not None:
                res_result = re_resolution_result
            elif self._resolver is not None:
                all_reg_domains = (
                    tuple(r.definition.id for r in self._registry.list_records())
                    if self._registry is not None
                    else ()
                )
                avail_slug_set = {d.slug for d in all_reg_domains}
                res_ctx = DomainResolutionContext(
                    id=f"domain-resolution-ctx-recomp-{session_id}",
                    session_id=session_id,
                    objective=f"Domain session recomposition for session '{session_id}'",
                    available_domains=all_reg_domains,
                    explicit_domains=tuple(
                        DomainId(slug=_extract_slug(s))
                        for s in effective_supporting
                        if _extract_slug(s) in avail_slug_set
                    ),
                    active_domains=(
                        tuple(
                            r.definition.id
                            for r in self._registry.list_records()
                            if r.status in (DomainStatus.ACTIVE, DomainStatus.DEGRADED)
                        )
                        if self._registry is not None
                        else ()
                    ),
                    current_profile=context.effective_profile,
                    current_workflow=(
                        context.active_workflow_refs[0]
                        if context.active_workflow_refs
                        else None
                    ),
                    requested_operations=context.available_operation_ids,
                    actor=str(request.actor or "system"),
                    temporal_reference=now_ts,
                )
                try:
                    res_result = self._resolver.resolve(res_ctx)
                except Exception:  # noqa: BLE001
                    res_result = None

                if (
                    res_result is None
                    or res_result.status != DomainResolutionStatus.RESOLVED
                ):
                    res_result = DomainResolutionResult(
                        id=last_resolution_id or f"domain-recomposition-{session_id}",
                        context_id=f"ctx-recomp-{session_id}",
                        status=DomainResolutionStatus.RESOLVED,
                        primary_domain=DomainId(slug=_extract_slug(effective_primary)),
                        supporting_domains=tuple(
                            DomainId(slug=_extract_slug(s))
                            for s in effective_supporting
                        ),
                        confidence=0.0,
                        resolved_at=now_ts,
                    )
            else:
                res_result = DomainResolutionResult(
                    id=last_resolution_id or f"domain-recomposition-{session_id}",
                    context_id=f"ctx-recomp-{session_id}",
                    status=DomainResolutionStatus.RESOLVED,
                    primary_domain=DomainId(slug=_extract_slug(effective_primary)),
                    supporting_domains=tuple(
                        DomainId(slug=_extract_slug(s)) for s in effective_supporting
                    ),
                    confidence=0.0,
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

            composition_id = (
                getattr(composed, "id", None) or f"domain-composition-{session_id}"
            )

            if re_resolution_result is not None:
                new_transition = DomainSessionTransition(
                    previous_primary_domain=context.primary_domain,
                    new_primary_domain=effective_primary,
                    previous_supporting_domains=context.supporting_domains,
                    new_supporting_domains=effective_supporting,
                    reason_code="RE_RESOLUTION",
                    resolution_id=re_resolution_result.id,
                    composition_id=composition_id,
                    occurred_at=now_ts,
                )
            elif status is DomainSessionResumeStatus.RECOMPOSED:
                new_transition = DomainSessionTransition(
                    previous_primary_domain=context.primary_domain,
                    new_primary_domain=effective_primary,
                    previous_supporting_domains=context.supporting_domains,
                    new_supporting_domains=effective_supporting,
                    reason_code="RECOMPOSITION_SUPPORTING_DISABLED",
                    resolution_id=last_resolution_id,
                    composition_id=composition_id,
                    occurred_at=now_ts,
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
                status = merge_resume_status(status, wf_status)
            if status in (
                DomainSessionResumeStatus.FAILED,
                DomainSessionResumeStatus.BLOCKED,
                DomainSessionResumeStatus.INCOMPATIBLE,
            ):
                return DomainSessionResumeResult(
                    status=status,
                    session_id=session_id,
                    previous_revision=previous_revision,
                    resumed_revision=previous_revision,
                    context=None,
                    checks=tuple(checks),
                    warnings=tuple(warnings),
                    blocking_findings=(
                        wf_check.message
                        if wf_check
                        else f"Workflow validation resulted in {status.value}",
                    ),
                    recorded_resumption=False,
                )
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

        # Invalidate questions targeting domains removed during recomposition/re-resolution
        if (
            status
            in (
                DomainSessionResumeStatus.RECOMPOSED,
                DomainSessionResumeStatus.RE_RESOLVED,
            )
            and recovered_questions
        ):
            active_slugs = {_extract_slug(effective_primary)} | {
                _extract_slug(s) for s in effective_supporting
            }
            prev_slugs = {_extract_slug(context.primary_domain)} | {
                _extract_slug(s) for s in context.supporting_domains
            }
            removed_slugs = prev_slugs - active_slugs
            if removed_slugs:
                retained_q = []
                dropped_q = []
                for q in recovered_questions:
                    q_lower = q.lower()
                    if any(slug in q_lower for slug in removed_slugs):
                        dropped_q.append(q)
                    else:
                        retained_q.append(q)
                recovered_questions = tuple(retained_q)
                if dropped_q:
                    warnings.append(
                        f"Dropped {len(dropped_q)} question(s) from removed domain(s): {sorted(removed_slugs)}"
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

        # 8.5 Drift impact and dependency invalidation (MAJOR-01, MAJOR-02)
        has_drift = any(c.status is DomainSessionCheckStatus.DRIFT for c in checks)
        if has_drift:
            status = merge_resume_status(
                status, DomainSessionResumeStatus.REPLAN_REQUIRED
            )

        if recovered_questions:
            status = merge_resume_status(
                status, DomainSessionResumeStatus.WAITING_FOR_USER
            )
        elif recovered_approvals:
            status = merge_resume_status(
                status, DomainSessionResumeStatus.WAITING_FOR_APPROVAL
            )

        has_version_change = any(
            c.status
            in (
                DomainSessionCheckStatus.CHANGED,
                DomainSessionCheckStatus.INCOMPATIBLE,
                DomainSessionCheckStatus.DRIFT,
            )
            and c.name.startswith("domain_version_")
            for c in checks
        )
        is_material_change = (
            has_drift
            or has_version_change
            or status
            in (
                DomainSessionResumeStatus.RECOMPOSED,
                DomainSessionResumeStatus.RE_RESOLVED,
                DomainSessionResumeStatus.REPLAN_REQUIRED,
            )
        )

        if is_material_change:
            effective_partial_results: tuple[str, ...] = ()
            effective_trace_refs: tuple[str, ...] = ()
            if context.partial_result_refs or context.trace_refs:
                warnings.append(
                    "Stale partial results and traces invalidated due to material session changes"
                )
            if self._next_step_reconstructor is not None:
                next_step = self._next_step_reconstructor(context, status)
            elif context.next_recommended_step is not None:
                next_step = "replan_execution"
            else:
                next_step = None
        else:
            effective_partial_results = context.partial_result_refs
            effective_trace_refs = context.trace_refs
            if self._next_step_reconstructor is not None:
                next_step = self._next_step_reconstructor(context, status)
            else:
                next_step = context.next_recommended_step

        # 9.5 Current accepted domain versions persistence (MAJOR-01)
        accepted_domain_versions = dict(context.domain_versions)
        if self._registry is not None:
            p_rec = self._registry.get_record(_extract_slug(effective_primary))
            if p_rec is not None:
                accepted_domain_versions[effective_primary] = str(
                    p_rec.definition.version
                )
            for sup in effective_supporting:
                s_rec = self._registry.get_record(_extract_slug(sup))
                if s_rec is not None:
                    accepted_domain_versions[sup] = str(s_rec.definition.version)

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
            domain_versions=accepted_domain_versions,
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
            partial_result_refs=effective_partial_results,
            trace_refs=effective_trace_refs,
            domain_transitions=transitions,
            last_resolution_id=last_resolution_id,
            next_recommended_step=next_step,
            revision=previous_revision + 1,
            updated_at=now_ts,
            metadata=dict(context.metadata),
        )

        # 11. Authoritative shared-session persistence boundary.
        # The generic shared SessionStore is the durable source of truth.
        # Legacy persistence_updater callbacks are never sufficient evidence
        # of a committed resumption.
        try:
            committed_context = self._shared_session_adapter.save_domain_session(
                resumed_context,
                expected_previous_revision=previous_revision,
            )
        except Exception:  # noqa: BLE001
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.FAILED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=tuple(checks),
                warnings=tuple(warnings),
                blocking_findings=("Shared session persistence failure",),
                recorded_resumption=False,
            )

        if (
            not isinstance(committed_context, DomainSessionContext)
            or committed_context.session_id != session_id
            or committed_context.revision != resumed_context.revision
        ):
            return DomainSessionResumeResult(
                status=DomainSessionResumeStatus.FAILED,
                session_id=session_id,
                previous_revision=previous_revision,
                resumed_revision=previous_revision,
                context=None,
                checks=tuple(checks),
                warnings=tuple(warnings),
                blocking_findings=("Shared session commit verification failed",),
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
            context=committed_context,
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
