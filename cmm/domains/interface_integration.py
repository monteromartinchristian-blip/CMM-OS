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

from typing import Protocol, runtime_checkable

from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainCenterDomainView,
    DomainCenterView,
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
    DomainInterfaceStatus,
    DomainInterfaceViewKind,
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
        return DomainInterfaceProjection(
            projection_id=f"interface-projection:{request.request_id}",
            request_id=request.request_id,
            resolution_reference_id=resolution.id,
            composition_reference_id=composition.id,
            session_reference_id=request.session_reference_id,
            conversational=conversational,
            selector=None,
            domain_center=domain_center,
            cross_domain=None,
            review_center=None,
            content_digest="",
        )
