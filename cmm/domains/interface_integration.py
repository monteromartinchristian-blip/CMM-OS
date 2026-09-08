"""Phase 10.45 — Domain Interface Integration.

Thin, stateless, interface-neutral integration boundary over canonical Domain
Intelligence authority. ``project()`` verifies canonical coherence and returns
immutable interface projections; selector intents (added in later blocks)
delegate only to existing canonical authority. View assembly is read-only over
the canonical inputs passed in: conversational state honors presentation
display visibility, and the Domain Center read-projects registry lifecycle
state plus canonical observability authority without ever fabricating content.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from cmm.agent_runtime.approval_contracts import ApprovalRequest
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import ApprovalRequestStatus
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextSnapshot,
    CrossDomainResult,
)
from cmm.domains.enums import (
    CrossDomainStatus,
    DomainCompositionStatus,
    DomainResolutionStatus,
)
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    CrossDomainInterfaceView,
    DomainCenterDomainView,
    DomainCenterView,
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
    DomainInterfaceStatus,
    DomainInterfaceViewKind,
    DomainReviewCenterView,
    DomainReviewItemView,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeProjection,
)
from cmm.domains.observability_contracts import DomainObservabilityReport
from cmm.domains.presentation_contracts import (
    DomainPresentationItemType,
    DomainPresentationPlan,
    DomainPresentationValidationState,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.session_contracts import DomainSessionContext

__all__ = [
    "DefaultDomainInterfaceIntegrator",
    "DomainInterfaceIntegrator",
]


@runtime_checkable
class DomainInterfaceIntegrator(Protocol):
    """Stateless interface projection authority."""

    def project(
        self,
        *,
        request: DomainInterfaceProjectionRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        presentation: DomainPresentationPlan | None = None,
        session: DomainSessionContext | None = None,
        memory_knowledge: DomainMemoryKnowledgeProjection | None = None,
        registry: DomainRegistry | None = None,
        observability_report: DomainObservabilityReport | None = None,
        cross_domain_result: CrossDomainResult | None = None,
        cross_domain_snapshot: CrossDomainContextSnapshot | None = None,
        approvals: tuple[ApprovalRequest, ...] | None = None,
    ) -> DomainInterfaceProjection:
        raise NotImplementedError


def _validate_authority(
    *,
    request: DomainInterfaceProjectionRequest,
    resolution: DomainResolutionResult,
    composition: DomainComposition,
    presentation: DomainPresentationPlan | None,
    session: DomainSessionContext | None,
    memory_knowledge: DomainMemoryKnowledgeProjection | None,
    registry: DomainRegistry | None,
    observability_report: DomainObservabilityReport | None,
    cross_domain_result: CrossDomainResult | None,
    cross_domain_snapshot: CrossDomainContextSnapshot | None,
    approvals: tuple[ApprovalRequest, ...] | None,
) -> None:
    """Verify exact canonical authority coherence, failing closed on any doubt."""
    if type(resolution) is not DomainResolutionResult:
        raise DomainInterfaceAuthorityError(
            "resolution must be a canonical DomainResolutionResult"
        )
    if resolution.status is not DomainResolutionStatus.RESOLVED:
        raise DomainInterfaceAuthorityError(
            "resolution must be RESOLVED for interface projection"
        )
    if type(composition) is not DomainComposition:
        raise DomainInterfaceAuthorityError(
            "composition must be a canonical DomainComposition"
        )
    if composition.status not in (
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    ):
        raise DomainInterfaceAuthorityError(
            "composition status must be COMPOSED or PARTIAL"
        )
    if request.resolution_reference_id != resolution.id:
        raise DomainInterfaceAuthorityError("resolution reference mismatch")
    if request.composition_reference_id != composition.id:
        raise DomainInterfaceAuthorityError("composition reference mismatch")
    if composition.resolution_id != resolution.id:
        raise DomainInterfaceAuthorityError("composition resolution mismatch")
    if resolution.primary_domain is None or str(composition.primary_domain) != str(
        resolution.primary_domain
    ):
        raise DomainInterfaceAuthorityError(
            "resolution and composition primary domains diverge"
        )
    if frozenset(str(d) for d in composition.supporting_domains) != frozenset(
        str(d) for d in resolution.supporting_domains
    ):
        raise DomainInterfaceAuthorityError(
            "composition supporting domains diverge from resolution"
        )
    if presentation is not None and type(presentation) is not DomainPresentationPlan:
        raise DomainInterfaceAuthorityError(
            "presentation must be a canonical DomainPresentationPlan"
        )
    if presentation is not None and presentation.composition_id != composition.id:
        raise DomainInterfaceAuthorityError("presentation composition binding mismatch")
    if session is not None:
        if type(session) is not DomainSessionContext:
            raise DomainInterfaceAuthorityError(
                "session must be a canonical DomainSessionContext"
            )
        if (
            request.session_reference_id is None
            or session.session_id != request.session_reference_id
        ):
            raise DomainInterfaceAuthorityError("session reference mismatch")
    if (
        memory_knowledge is not None
        and type(memory_knowledge) is not DomainMemoryKnowledgeProjection
    ):
        raise DomainInterfaceAuthorityError(
            "memory_knowledge must be a canonical DomainMemoryKnowledgeProjection"
        )
    if registry is not None and type(registry) is not DomainRegistry:
        raise DomainInterfaceAuthorityError(
            "registry must be a canonical DomainRegistry"
        )
    if (
        observability_report is not None
        and type(observability_report) is not DomainObservabilityReport
    ):
        raise DomainInterfaceAuthorityError(
            "observability_report must be a canonical DomainObservabilityReport"
        )
    if cross_domain_result is not None:
        if type(cross_domain_result) is not CrossDomainResult:
            raise DomainInterfaceAuthorityError(
                "cross_domain_result must be a canonical CrossDomainResult"
            )
        if cross_domain_result.composition_id is None:
            raise DomainInterfaceAuthorityError(
                "cross-domain result declares no composition binding"
            )
        if cross_domain_result.composition_id != composition.id:
            raise DomainInterfaceAuthorityError(
                "cross-domain result composition binding mismatch"
            )
    if cross_domain_snapshot is not None:
        if type(cross_domain_snapshot) is not CrossDomainContextSnapshot:
            raise DomainInterfaceAuthorityError(
                "cross_domain_snapshot must be a canonical CrossDomainContextSnapshot"
            )
        if cross_domain_snapshot.composition_id is None:
            raise DomainInterfaceAuthorityError(
                "cross-domain snapshot declares no composition binding"
            )
        if cross_domain_snapshot.composition_id != composition.id:
            raise DomainInterfaceAuthorityError(
                "cross-domain snapshot composition binding mismatch"
            )
    if approvals is not None:
        if isinstance(approvals, str) or not isinstance(approvals, Sequence):
            raise DomainInterfaceAuthorityError(
                "approvals must be a sequence of canonical ApprovalRequest entries"
            )
        for approval in approvals:
            if type(approval) is not ApprovalRequest:
                raise DomainInterfaceAuthorityError(
                    "approvals must contain only canonical ApprovalRequest entries"
                )


def _visible_item_ref_ids(plan: DomainPresentationPlan) -> frozenset[str]:
    """Effective display visibility: item visible AND placed in a visible section.

    An item that is not placed in any section has no proven display slot and is
    therefore treated as not visible. Failing closed never leaks hidden items.
    """
    section_visibility_by_ref: dict[str, list[bool]] = {}
    for section in plan.sections:
        for ref in section.item_refs:
            section_visibility_by_ref.setdefault(ref, []).append(section.visible)
    visible: set[str] = set()
    for item in plan.item_refs:
        if not item.visible:
            continue
        section_visibility = section_visibility_by_ref.get(item.ref_id)
        if section_visibility and any(section_visibility):
            visible.add(item.ref_id)
    return frozenset(visible)


def _visible_group_refs(
    plan: DomainPresentationPlan,
    group_field: str,
    visible_ref_ids: frozenset[str],
) -> tuple[str, ...]:
    """Group refs whose underlying display item is effectively visible."""
    item_refs = frozenset(item.ref_id for item in plan.item_refs)
    return tuple(
        ref
        for ref in getattr(plan, group_field)
        if ref in visible_ref_ids and ref in item_refs
    )


def _visible_item_refs_of_type(
    plan: DomainPresentationPlan,
    item_type: DomainPresentationItemType,
    visible_ref_ids: frozenset[str],
) -> tuple[str, ...]:
    items = sorted(
        (
            item
            for item in plan.item_refs
            if item.ref_id in visible_ref_ids and item.item_type is item_type
        ),
        key=lambda item: (item.source_order, item.ref_id),
    )
    return tuple(item.ref_id for item in items)


def _minimum_visible_confidence(
    plan: DomainPresentationPlan, visible_ref_ids: frozenset[str]
) -> float | None:
    confidences = [
        item.confidence
        for item in plan.item_refs
        if item.ref_id in visible_ref_ids and item.confidence is not None
    ]
    return min(confidences) if confidences else None


def _project_conversational(
    *,
    resolution: DomainResolutionResult,
    composition: DomainComposition,
    presentation: DomainPresentationPlan | None,
) -> ConversationalDomainView:
    """Assemble the authorized conversational view without deriving content."""
    visible_ref_ids = (
        _visible_item_ref_ids(presentation) if presentation is not None else frozenset()
    )
    if presentation is not None:
        domain_tokens = {
            token
            for item in presentation.item_refs
            if item.ref_id in visible_ref_ids
            for token in item.domain_ids
        }
        supporting_domains = tuple(
            str(domain)
            for domain in resolution.supporting_domains
            if str(domain) in domain_tokens or domain.slug in domain_tokens
        )
    else:
        supporting_domains = tuple(str(d) for d in resolution.supporting_domains)
    confidence = (
        _minimum_visible_confidence(presentation, visible_ref_ids)
        if presentation is not None
        else None
    )
    if (
        presentation is not None
        and presentation.validation_state is DomainPresentationValidationState.BLOCKED
    ):
        status = DomainInterfaceStatus.BLOCKED
    elif composition.status is DomainCompositionStatus.PARTIAL:
        status = DomainInterfaceStatus.PARTIAL
    else:
        status = DomainInterfaceStatus.READY
    refs = {
        "workflow_refs": (),
        "question_refs": (),
        "approval_refs": (),
        "warning_refs": (),
        "memory_proposal_refs": (),
    }
    if presentation is not None:
        refs["workflow_refs"] = _visible_group_refs(
            presentation, "workflow_refs", visible_ref_ids
        )
        refs["question_refs"] = _visible_group_refs(
            presentation, "question_refs", visible_ref_ids
        )
        refs["approval_refs"] = _visible_group_refs(
            presentation, "approval_refs", visible_ref_ids
        )
        refs["warning_refs"] = _visible_group_refs(
            presentation, "warning_refs", visible_ref_ids
        )
        refs["memory_proposal_refs"] = _visible_group_refs(
            presentation, "memory_proposal_refs", visible_ref_ids
        )
    assert resolution.primary_domain is not None
    return ConversationalDomainView(
        primary_domain=str(resolution.primary_domain),
        supporting_domains=supporting_domains,
        workflow_refs=refs["workflow_refs"],
        question_refs=refs["question_refs"],
        approval_refs=refs["approval_refs"],
        source_refs=(
            _visible_item_refs_of_type(
                presentation, DomainPresentationItemType.FINDING, visible_ref_ids
            )
            if presentation is not None
            else ()
        ),
        contradiction_refs=(
            _visible_item_refs_of_type(
                presentation,
                DomainPresentationItemType.CONTRADICTION,
                visible_ref_ids,
            )
            if presentation is not None
            else ()
        ),
        # No canonical result carrier exists in this phase: never fabricated.
        result_refs=(),
        memory_proposal_refs=refs["memory_proposal_refs"],
        confidence=confidence,
        warning_refs=refs["warning_refs"],
        status=status,
    )


def _metric_refs_for(
    definition: DomainDefinition | None,
    observability_report: DomainObservabilityReport | None,
) -> tuple[str, ...]:
    if observability_report is None or definition is None:
        return ()
    domain_ref = str(definition.id)
    slug = definition.id.slug
    names = {
        measurement.name
        for measurement in observability_report.metrics.measurements
        if domain_ref in measurement.evidence_reference_ids
        or slug in measurement.evidence_reference_ids
    }
    return tuple(sorted(names))


def _error_refs_for(
    definition: DomainDefinition | None,
    observability_report: DomainObservabilityReport | None,
) -> tuple[str, ...]:
    if observability_report is None or definition is None:
        return ()
    domain_ref = str(definition.id)
    slug = definition.id.slug
    refs: set[str] = set()
    for entry in observability_report.log_entries:
        if entry.category != "error":
            continue
        if entry.primary_domain not in (domain_ref, slug):
            continue
        refs.update(entry.reference_ids)
    return tuple(sorted(refs))


def _project_domain_center(
    *,
    registry: DomainRegistry,
    observability_report: DomainObservabilityReport | None,
) -> DomainCenterView:
    """Read-only Domain Center projection over registry lifecycle records."""
    entries: list[DomainCenterDomainView] = []
    slugs = sorted({record.domain_id for record in registry.list_records()})
    for slug in slugs:
        record = registry.get_record(slug)
        if record is None:
            continue
        definition = record.definition
        entries.append(
            DomainCenterDomainView(
                domain_id=str(definition.id),
                status=record.status.value,
                enabled=definition.enabled,
                version=definition.version,
                capability_refs=tuple(
                    capability.name for capability in definition.capabilities
                ),
                permission_refs=definition.permissions,
                operation_refs=definition.operations,
                workflow_refs=definition.workflows,
                metric_refs=_metric_refs_for(definition, observability_report),
                error_refs=_error_refs_for(definition, observability_report),
                # No canonical domain update source exists; never claim updates.
                update_status="unknown",
            )
        )
    return DomainCenterView(domains=tuple(entries))


def _composition_membership(composition: DomainComposition) -> frozenset[str]:
    refs = {str(composition.primary_domain)}
    refs.update(str(domain) for domain in composition.supporting_domains)
    return frozenset(refs)


def _authorized_transfer_refs(
    snapshot: CrossDomainContextSnapshot,
    membership: frozenset[str],
) -> tuple[str, ...]:
    """Identifiers of transfers whose authorization is canonically established.

    Only transfers present in the accepted canonical transfer list whose content
    is neither private nor sealed and whose endpoints belong to the composed
    domain set are surfaced; denied transfers never exist in canonical state.
    """
    identifiers: set[str] = set()
    for transfer in snapshot.transfers:
        if transfer.private or not transfer.transferable:
            continue
        if str(transfer.source_domain) not in membership:
            continue
        if str(transfer.target_domain) not in membership:
            continue
        identifiers.add(transfer.identifier)
    return tuple(sorted(identifiers))


def _canonical_dependencies(
    result: CrossDomainResult | None,
    snapshot: CrossDomainContextSnapshot | None,
) -> tuple[object, ...]:
    if result is not None:
        return result.dependencies
    if snapshot is not None:
        return snapshot.dependencies
    return ()


def _dependency_refs(
    dependencies: tuple[object, ...], membership: frozenset[str]
) -> tuple[str, ...]:
    refs: set[str] = set()
    for dependency in dependencies:
        if str(dependency.source_domain) not in membership:
            continue
        if str(dependency.target_domain) not in membership:
            continue
        # No canonical dependency id exists upstream; refs copy the canonical
        # endpoints and the kind verbatim and never relabel the relation.
        refs.add(
            f"dependency:{dependency.source_domain.slug}:"
            f"{dependency.target_domain.slug}:{dependency.kind}"
        )
    return tuple(sorted(refs))


def _canonical_contradictions(
    result: CrossDomainResult | None,
    snapshot: CrossDomainContextSnapshot | None,
) -> tuple[object, ...]:
    if result is not None:
        return result.contradictions
    if snapshot is not None:
        return snapshot.contradictions
    return ()


def _unresolved_conflict_refs(
    contradictions: tuple[object, ...], membership: frozenset[str]
) -> tuple[str, ...]:
    refs: set[str] = set()
    for contradiction in contradictions:
        if contradiction.resolved:
            continue
        if not all(str(domain) in membership for domain in contradiction.domains):
            continue
        refs.add(contradiction.id)
    return tuple(sorted(refs))


def _cross_domain_status(
    composition: DomainComposition,
    result: CrossDomainResult | None,
) -> DomainInterfaceStatus:
    """Map canonical state to interface status without ever strengthening it."""
    if composition.status is DomainCompositionStatus.PARTIAL:
        return DomainInterfaceStatus.PARTIAL
    if result is None:
        return DomainInterfaceStatus.PENDING
    if result.status is CrossDomainStatus.COMPLETED:
        return DomainInterfaceStatus.READY
    if result.status is CrossDomainStatus.PARTIAL:
        return DomainInterfaceStatus.PARTIAL
    if result.status is CrossDomainStatus.LIMIT_REACHED:
        return DomainInterfaceStatus.PARTIAL
    # BLOCKED, FAILED and REQUIRES_REVIEW cannot be presented as ready.
    return DomainInterfaceStatus.BLOCKED


def _project_cross_domain(
    *,
    composition: DomainComposition,
    result: CrossDomainResult | None,
    snapshot: CrossDomainContextSnapshot | None,
) -> CrossDomainInterfaceView:
    """Project the already-resolved cross-domain state, never recalculating it."""
    membership = _composition_membership(composition)
    transfer_refs = (
        _authorized_transfer_refs(snapshot, membership) if snapshot is not None else ()
    )
    dependency_refs = _dependency_refs(
        _canonical_dependencies(result, snapshot), membership
    )
    conflict_refs = _unresolved_conflict_refs(
        _canonical_contradictions(result, snapshot), membership
    )
    return CrossDomainInterfaceView(
        primary_domain=str(composition.primary_domain),
        supporting_domains=tuple(str(d) for d in composition.supporting_domains),
        transfer_refs=transfer_refs,
        dependency_refs=dependency_refs,
        conflict_refs=conflict_refs,
        consolidated_result_ref=result.id if result is not None else None,
        status=_cross_domain_status(composition, result),
    )


# Review Center category tokens are view-owned labels for canonical review
# evidence; upstream defines no review-category enum to reference.
_REVIEW_CATEGORY_OPERATION_APPROVAL = "operation_approval"
_REVIEW_CATEGORY_CROSS_DOMAIN_ACCESS = "cross_domain_access"
_REVIEW_CATEGORY_SENSITIVE_PERSISTENCE = "sensitive_persistence"
_REVIEW_CATEGORY_EXTERNAL_ACTION = "external_action"

_PERMISSION_REVIEW_CATEGORIES = {
    PermissionCapability.DOMAIN_CROSS_ACCESS: _REVIEW_CATEGORY_CROSS_DOMAIN_ACCESS,
    PermissionCapability.SENSITIVE_INFERENCE_PERSIST: (
        _REVIEW_CATEGORY_SENSITIVE_PERSISTENCE
    ),
    PermissionCapability.SEARCH_EXTERNAL: _REVIEW_CATEGORY_EXTERNAL_ACTION,
    PermissionCapability.MODEL_EXTERNAL: _REVIEW_CATEGORY_EXTERNAL_ACTION,
    PermissionCapability.COMMUNICATION_EXTERNAL: _REVIEW_CATEGORY_EXTERNAL_ACTION,
}

_REVIEW_OPEN_STATES = frozenset(
    {ApprovalRequestStatus.PENDING, ApprovalRequestStatus.POSTPONED}
)


def _review_item_evidence(
    approval: ApprovalRequest,
    membership: frozenset[str],
) -> tuple[str, str, str | None, str | None] | None:
    """Classify one canonical approval, returning (category, domain, reason_ref, session_ref).

    Typed permission evidence wins when present; only canonical membership and
    open review states are surfaced. Uncategorizable approvals stay out of the
    aggregate instead of inventing a review category for them.
    """
    if approval.status not in _REVIEW_OPEN_STATES:
        return None
    par = approval.permission_requirement
    if par is not None:
        if par.domain_id not in membership:
            return None
        category = _PERMISSION_REVIEW_CATEGORIES.get(par.action)
        if category is None:
            return None
        return category, par.domain_id, par.reason_code, par.session_id
    operation_codes = tuple(
        code for code in approval.reason_codes if code.startswith("domain_operation.")
    )
    if not operation_codes:
        return None
    metadata = approval.metadata
    if metadata.get("scope") != "domain_operation":
        return None
    primary_domain_id = metadata.get("primary_domain_id")
    if not isinstance(primary_domain_id, str) or primary_domain_id not in membership:
        return None
    return (
        _REVIEW_CATEGORY_OPERATION_APPROVAL,
        primary_domain_id,
        operation_codes[0],
        None,
    )


def _project_review_center(
    *,
    approvals: tuple[ApprovalRequest, ...],
    composition: DomainComposition,
) -> DomainReviewCenterView:
    """Aggregate canonical open review-required references for the composition."""
    membership = _composition_membership(composition)
    items: list[DomainReviewItemView] = []
    for approval in approvals:
        evidence = _review_item_evidence(approval, membership)
        if evidence is None:
            continue
        category, domain_id, reason_ref, session_ref = evidence
        items.append(
            DomainReviewItemView(
                review_ref=approval.id,
                category=category,
                state=approval.status.value,
                domain_id=domain_id,
                operation_ref=approval.operation_id,
                workflow_ref=approval.workflow_id,
                session_ref=session_ref,
                reason_ref=reason_ref,
            )
        )
    return DomainReviewCenterView(items=tuple(items))


class DefaultDomainInterfaceIntegrator:
    """Default implementation of ``DomainInterfaceIntegrator``.

    Stateless: ``project()`` performs no store lookups and no writes. View
    assembly blocks are added incrementally over canonical inputs only.
    """

    def __init__(self) -> None:
        pass

    def project(
        self,
        *,
        request: DomainInterfaceProjectionRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
        presentation: DomainPresentationPlan | None = None,
        session: DomainSessionContext | None = None,
        memory_knowledge: DomainMemoryKnowledgeProjection | None = None,
        registry: DomainRegistry | None = None,
        observability_report: DomainObservabilityReport | None = None,
        cross_domain_result: CrossDomainResult | None = None,
        cross_domain_snapshot: CrossDomainContextSnapshot | None = None,
        approvals: tuple[ApprovalRequest, ...] | None = None,
    ) -> DomainInterfaceProjection:
        _validate_authority(
            request=request,
            resolution=resolution,
            composition=composition,
            presentation=presentation,
            session=session,
            memory_knowledge=memory_knowledge,
            registry=registry,
            observability_report=observability_report,
            cross_domain_result=cross_domain_result,
            cross_domain_snapshot=cross_domain_snapshot,
            approvals=approvals,
        )
        requested = frozenset(request.requested_views)
        conversational = None
        if DomainInterfaceViewKind.CONVERSATIONAL in requested:
            conversational = _project_conversational(
                resolution=resolution,
                composition=composition,
                presentation=presentation,
            )
        domain_center = None
        if DomainInterfaceViewKind.DOMAIN_CENTER in requested and registry is not None:
            domain_center = _project_domain_center(
                registry=registry,
                observability_report=observability_report,
            )
        cross_domain = None
        if DomainInterfaceViewKind.CROSS_DOMAIN in requested and (
            cross_domain_result is not None or cross_domain_snapshot is not None
        ):
            cross_domain = _project_cross_domain(
                composition=composition,
                result=cross_domain_result,
                snapshot=cross_domain_snapshot,
            )
        review_center = None
        if DomainInterfaceViewKind.REVIEW_CENTER in requested and approvals is not None:
            review_center = _project_review_center(
                approvals=approvals,
                composition=composition,
            )
        return DomainInterfaceProjection(
            projection_id=f"interface-projection:{request.request_id}",
            request_id=request.request_id,
            resolution_reference_id=resolution.id,
            composition_reference_id=composition.id,
            session_reference_id=request.session_reference_id,
            conversational=conversational,
            selector=None,
            domain_center=domain_center,
            cross_domain=cross_domain,
            review_center=review_center,
            content_digest="",
        )
