"""Tests for the Phase 10.45 Domain Interface integration core.

Covers canonical authority binding (fail-closed projection), projection purity,
and the interface views assembled over canonical resolution/composition state,
presentation visibility, registry lifecycle state and observability authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType, SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from cmm.agent_runtime.approval_contracts import ApprovalRequest
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionApprovalRequirement,
    PermissionCapability,
)
from cmm.agent_runtime.enums import ApprovalRequestStatus
from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
)
from cmm.domains.contracts import (
    DomainCapability,
    DomainDefinition,
    DomainMetadata,
)
from cmm.domains.cross_domain_contracts import (
    CrossDomainContextSnapshot,
    CrossDomainContextTransfer,
    CrossDomainContradiction,
    CrossDomainDecision,
    CrossDomainDependency,
    CrossDomainLimits,
    CrossDomainResult,
)
from cmm.domains.enums import (
    CrossDomainStage,
    CrossDomainStatus,
    DomainCompositionStatus,
    DomainKind,
    DomainResolutionStatus,
    DomainStatus,
)
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceIntent,
    DomainInterfaceIntentKind,
    DomainInterfaceIntentResult,
    DomainInterfaceProjectionRequest,
    DomainInterfaceStatus,
    DomainInterfaceViewKind,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.observability_contracts import (
    DomainMetricMeasurement,
    DomainMetricsSnapshot,
    DomainMetricStatus,
    DomainObservabilityLogEntry,
    DomainObservabilityReport,
)
from cmm.domains.permission_contracts import (
    CrossDomainPermissionRequest,
    DomainPermissionPolicy,
    PermissionOutcome,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationPlan,
    DomainPresentationSectionPlan,
    DomainPresentationValidationState,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import (
    DomainResolutionReason,
    DomainResolutionResult,
)
from cmm.domains.selection_transition import (
    DefaultDomainSelectionTransitionCoordinator,
)
from cmm.domains.session_contracts import DomainSessionContext

if TYPE_CHECKING:
    # Static reference only; runtime construction stays lazy below because
    # test_domain_selection_transition imports fixtures from this module.
    from tests.domains.test_domain_selection_transition import (
        _CoordinatorEnvironment,
    )


def _make_presentation(**overrides: object) -> DomainPresentationPlan:
    values: dict[str, object] = {
        "plan_id": "presentation-plan:1",
        "request_id": "presentation-request:1",
        "composition_id": "composition:1",
        "policy_id": "presentation-policy:1",
        "output_intent": DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        "sections": (
            DomainPresentationSectionPlan(section_id="findings", item_refs=()),
        ),
    }
    values.update(overrides)
    return DomainPresentationPlan(**values)


def _make_resolution(
    resolution_id: str = "resolution:1",
    status: DomainResolutionStatus = DomainResolutionStatus.RESOLVED,
    primary_domain: str = "domain:health",
    supporting_domains: tuple[str, ...] = ("domain:general",),
    **overrides: object,
) -> DomainResolutionResult:
    values: dict[str, object] = {
        "id": resolution_id,
        "context_id": "ctx:interface:1",
        "status": status,
    }
    if status is DomainResolutionStatus.RESOLVED:
        values["primary_domain"] = DomainId(primary_domain.removeprefix("domain:"))
        values["supporting_domains"] = tuple(
            DomainId(d.removeprefix("domain:")) for d in supporting_domains
        )
    else:
        # Canonical non-RESOLVED invariants: BLOCKED requires rejected domains
        # and at least one blocking reason; everything else stays structurally
        # valid without a primary domain.
        values["primary_domain"] = None
        values["supporting_domains"] = ()
        if status is DomainResolutionStatus.BLOCKED:
            values["rejected_domains"] = (
                DomainId(primary_domain.removeprefix("domain:")),
            )
            values["reasons"] = (
                DomainResolutionReason(
                    code="domain:blocked",
                    message="blocked for interface projection test",
                    blocking=True,
                ),
            )
        else:
            values["rejected_domains"] = ()
    values.update(overrides)
    return DomainResolutionResult(**values)


def _make_composition(
    composition_id: str = "composition:1",
    resolution_id: str = "resolution:1",
    status: DomainCompositionStatus = DomainCompositionStatus.COMPOSED,
    primary_domain: str = "domain:health",
    supporting_domains: tuple[str, ...] = ("domain:general",),
    **overrides: object,
) -> DomainComposition:
    values: dict[str, object] = {
        "id": composition_id,
        "resolution_id": resolution_id,
        "status": status,
        "primary_domain": DomainId(primary_domain.removeprefix("domain:")),
        "supporting_domains": tuple(
            DomainId(d.removeprefix("domain:")) for d in supporting_domains
        ),
    }
    values.update(overrides)
    return DomainComposition(**values)


def _make_request(**overrides: object) -> DomainInterfaceProjectionRequest:
    values: dict[str, object] = {
        "request_id": "interface-request:1",
        "resolution_reference_id": "resolution:1",
        "composition_reference_id": "composition:1",
        "session_reference_id": "session:1",
    }
    values.update(overrides)
    return DomainInterfaceProjectionRequest(**values)


def _make_item(
    ref_id: str,
    item_type: DomainPresentationItemType,
    *,
    source_order: int,
    domain_ids: tuple[str, ...] = (),
    visible: bool = True,
    confidence: float | None = None,
    requires_provenance: bool = False,
) -> DomainPresentationItemRef:
    return DomainPresentationItemRef(
        ref_id=ref_id,
        item_type=item_type,
        source_order=source_order,
        domain_ids=domain_ids,
        visible=visible,
        confidence=confidence,
        requires_provenance=requires_provenance,
    )


def _make_presentation_with_items(
    items: tuple[DomainPresentationItemRef, ...],
    *,
    sections: tuple[DomainPresentationSectionPlan, ...] | None = None,
    approval_refs: tuple[str, ...] = (),
    question_refs: tuple[str, ...] = (),
    workflow_refs: tuple[str, ...] = (),
    warning_refs: tuple[str, ...] = (),
    memory_proposal_refs: tuple[str, ...] = (),
    validation_state: DomainPresentationValidationState = (
        DomainPresentationValidationState.VALID
    ),
    **overrides: object,
) -> DomainPresentationPlan:
    if sections is None:
        sections = (
            DomainPresentationSectionPlan(
                section_id="findings",
                item_refs=tuple(item.ref_id for item in items),
            ),
        )
    values: dict[str, object] = {
        "plan_id": "presentation-plan:1",
        "request_id": "presentation-request:1",
        "composition_id": "composition:1",
        "policy_id": "presentation-policy:1",
        "output_intent": DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        "sections": sections,
        "item_refs": items,
        "approval_refs": approval_refs,
        "question_refs": question_refs,
        "workflow_refs": workflow_refs,
        "warning_refs": warning_refs,
        "memory_proposal_refs": memory_proposal_refs,
        "validation_state": validation_state,
    }
    values.update(overrides)
    return DomainPresentationPlan(**values)


def _make_domain_definition(
    slug: str,
    version: str = "1.0.0",
    *,
    capabilities: tuple[DomainCapability, ...] = (),
    operations: tuple[str, ...] = (),
    workflows: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> DomainDefinition:
    return DomainDefinition(
        id=f"domain:{slug}",
        name=slug,
        display_name=f"Test {slug} Domain",
        version=version,
        kind=DomainKind.CORE,
        description=f"Test {slug} domain for interface projection",
        manifest_id=f"manifest:{slug}:{version}",
        capabilities=capabilities,
        operations=operations,
        workflows=workflows,
        permissions=permissions,
        metadata=DomainMetadata(author="tester", license="MIT"),
    )


def _make_capability(provider_slug: str, name: str) -> DomainCapability:
    return DomainCapability(
        name=name,
        kind="test",
        provided_by=f"domain:{provider_slug}",
        version="1.0.0",
    )


def _mark_degraded(registry: DomainRegistry, slug: str) -> DomainRegistryRecord:
    record = registry.get_record(slug)
    assert record is not None
    degraded = DomainRegistryRecord(
        definition=record.definition,
        status=DomainStatus.DEGRADED,
        registered_at=record.registered_at,
        updated_at=datetime.now(timezone.utc),
    )
    return registry.restore_record(degraded)


def _make_observability_report(
    *,
    measurements: tuple[DomainMetricMeasurement, ...] = (),
    log_entries: tuple[DomainObservabilityLogEntry, ...] = (),
) -> DomainObservabilityReport:
    generated_at = datetime.now(timezone.utc)
    return DomainObservabilityReport(
        generated_at=generated_at,
        log_entries=log_entries,
        metrics=DomainMetricsSnapshot(
            generated_at=generated_at, measurements=measurements
        ),
        health_results=(),
    )


def _make_transfer(
    *,
    source: str,
    target: str,
    identifier: str,
    kind: str = "finding",
    private: bool = False,
    transferable: bool = True,
) -> CrossDomainContextTransfer:
    return CrossDomainContextTransfer(
        source_domain=source,
        target_domain=target,
        kind=kind,
        identifier=identifier,
        value=f"value:{identifier}",
        reason="interface projection test transfer",
        provenance=("interface:test",),
        private=private,
        transferable=transferable,
    )


def _make_dependency(
    *,
    source: str,
    target: str,
    kind: str = "requires",
    description: str = "domain coordination",
    blocking: bool = False,
    satisfied: bool = True,
) -> CrossDomainDependency:
    return CrossDomainDependency(
        source_domain=source,
        target_domain=target,
        kind=kind,
        description=description,
        blocking=blocking,
        satisfied=satisfied,
        provenance=("interface:test",),
    )


def _make_contradiction(
    contradiction_id: str,
    *,
    domains: tuple[str, ...] = ("domain:health", "domain:general"),
    severity: str = "medium",
    resolved: bool = False,
    resolution: str | None = None,
    requires_review: bool = False,
) -> CrossDomainContradiction:
    return CrossDomainContradiction(
        id=contradiction_id,
        domains=domains,
        subject=f"subject of {contradiction_id}",
        statements=(f"statement of {contradiction_id}",),
        severity=severity,
        resolved=resolved,
        resolution=resolution,
        requires_review=requires_review,
        provenance=("interface:test",),
    )


def _make_decision(
    code: str,
    *,
    domain_slug: str | None = None,
    action: str = "cross-domain coordination decision",
    blocking: bool = False,
) -> CrossDomainDecision:
    return CrossDomainDecision(
        code=code,
        stage=CrossDomainStage.DOMAIN_EXECUTION,
        domain_id=DomainId(slug=domain_slug) if domain_slug is not None else None,
        action=action,
        blocking=blocking,
    )


def _make_cross_domain_snapshot(
    *,
    composition_id: str | None = "composition:1",
    transfers: tuple[CrossDomainContextTransfer, ...] = (),
    dependencies: tuple[CrossDomainDependency, ...] = (),
    contradictions: tuple[CrossDomainContradiction, ...] = (),
    decisions: tuple[CrossDomainDecision, ...] = (),
) -> CrossDomainContextSnapshot:
    return CrossDomainContextSnapshot(
        request_id="cross-domain-request:1",
        composition_id=composition_id,
        transfers=transfers,
        dependencies=dependencies,
        contradictions=contradictions,
        decisions=decisions,
        started_at=datetime.now(timezone.utc),
    )


def _make_cross_domain_result(
    *,
    result_id: str = "cross-domain-result:1",
    status: CrossDomainStatus = CrossDomainStatus.COMPLETED,
    composition_id: str | None = "composition:1",
    dependencies: tuple[CrossDomainDependency, ...] = (),
    contradictions: tuple[CrossDomainContradiction, ...] = (),
    decisions: tuple[CrossDomainDecision, ...] = (),
    **overrides: object,
) -> CrossDomainResult:
    started_at = datetime.now(timezone.utc)
    values: dict[str, object] = {
        "id": result_id,
        "status": status,
        "objective": "interface projection test objective",
        "request_id": "cross-domain-request:1",
        "composition_id": composition_id,
        "dependencies": dependencies,
        "contradictions": contradictions,
        "decisions": decisions,
        "trace_id": "trace:interface:1",
        "started_at": started_at,
        "completed_at": started_at,
    }
    values.update(overrides)
    return CrossDomainResult(**values)


def _make_par(
    *,
    action: PermissionCapability,
    requirement_id: str,
    actor_id: str = "actor:interface:1",
    session_id: str = "session:1",
    domain_id: str = "domain:health",
    resource_id: str | None = "resource:interface:1",
    operation_id: str | None = None,
    workflow_id: str | None = None,
    target_domain: str | None = None,
    reason_code: str = "approval_required",
) -> PermissionApprovalRequirement:
    return PermissionApprovalRequirement(
        requirement_id=requirement_id,
        action=action,
        actor_id=actor_id,
        session_id=session_id,
        domain_id=domain_id,
        resource_id=resource_id,
        operation_id=operation_id,
        workflow_id=workflow_id,
        target_domain=target_domain,
        fingerprint=f"{requirement_id}:{action.value}:{domain_id}",
        scope="request",
        reason_code=reason_code,
        risk="medium",
        one_time=True,
        reusable=False,
    )


def _make_approval(
    *,
    approval_id: str,
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    reason_codes: tuple[str, ...] = (),
    metadata: dict[str, object] | None = None,
    permission_requirement: PermissionApprovalRequirement | None = None,
    operation_id: str | None = None,
    workflow_id: str | None = None,
) -> ApprovalRequest:
    return ApprovalRequest(
        id=approval_id,
        title="Review Center interface projection test approval",
        description="Canonical approval request created for interface projection tests.",
        requested_by="agent-runtime",
        reason_codes=reason_codes,
        metadata=metadata if metadata is not None else {},
        permission_requirement=permission_requirement,
        operation_id=operation_id,
        workflow_id=workflow_id,
        status=status,
    )


def _make_operation_approval(
    approval_id: str,
    *,
    status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    reason_code: str = "domain_operation.destructive",
    metadata_scope: str = "domain_operation",
    primary_domain: str = "domain:health",
    supporting_domains: tuple[str, ...] = ("domain:general",),
    operation_id: str | None = "operation:1",
    workflow_id: str | None = "workflow:1",
) -> ApprovalRequest:
    return _make_approval(
        approval_id=approval_id,
        status=status,
        reason_codes=(reason_code,),
        metadata=MappingProxyType(
            {
                "scope": metadata_scope,
                "primary_domain_id": primary_domain,
                "supporting_domain_ids": list(supporting_domains),
            }
        ),
        operation_id=operation_id,
        workflow_id=workflow_id,
    )


def _make_memory_knowledge_request(
    **overrides: object,
) -> DomainMemoryKnowledgeProjectionRequest:
    values: dict[str, object] = {
        "request_id": "memory-knowledge-request:1",
        "primary_domain": DomainId("health"),
        "supporting_domains": (DomainId("general"),),
        "memory_view_id": "memory-view:1",
        "memory_view_digest": "0" * 64,
        "resolution_reference_id": "resolution:1",
        "composition_reference_id": "composition:1",
        "permission_decision_ids": (),
        "requested_capabilities": (),
    }
    values.update(overrides)
    return DomainMemoryKnowledgeProjectionRequest(**values)


def _make_memory_knowledge_projection(
    request: DomainMemoryKnowledgeProjectionRequest,
) -> DomainMemoryKnowledgeProjection:
    return DomainMemoryKnowledgeProjection.create(
        request_id=request.request_id,
        request_digest=request.digest,
        memory_view_id=request.memory_view_id,
        memory_view_digest=request.memory_view_digest,
        selected_reference_ids=(),
        shared_identity_reference_ids=(),
        relation_refs=(),
    )


def _project_views(env: _CanonicalProjectionEnvironment, **overrides: object):
    kwargs: dict[str, object] = {
        "request": env.request,
        "resolution": env.resolution,
        "composition": env.composition,
    }
    kwargs.update(overrides)
    return env.integrator.project(**kwargs)


class _CanonicalProjectionEnvironment:
    """Mutable builder over one canonical resolution/composition/request set."""

    def __init__(
        self,
        *,
        request: DomainInterfaceProjectionRequest,
        resolution: DomainResolutionResult,
        composition: DomainComposition,
    ) -> None:
        self.request = request
        self.resolution = resolution
        self.composition = composition
        self.registry = DomainRegistry()
        self.integrator = DefaultDomainInterfaceIntegrator()

    @property
    def project_kwargs(self) -> dict[str, object]:
        return {
            "request": self.request,
            "resolution": self.resolution,
            "composition": self.composition,
        }

    def project_interface(self):
        return self.integrator.project(**self.project_kwargs)

    def snapshot_state(self) -> tuple[object, ...]:
        return (
            self.request.to_dict(),
            self.resolution.to_dict(),
            self.composition.to_dict(),
            self.registry.list_records(),
            self.registry.snapshot_state(),
        )

    def with_request_resolution_reference(
        self, reference: str
    ) -> _CanonicalProjectionEnvironment:
        return _CanonicalProjectionEnvironment(
            request=_make_request(resolution_reference_id=reference),
            resolution=self.resolution,
            composition=self.composition,
        )

    def with_resolution_id(self, resolution_id: str) -> _CanonicalProjectionEnvironment:
        return _CanonicalProjectionEnvironment(
            request=self.request,
            resolution=_make_resolution(resolution_id=resolution_id),
            composition=self.composition,
        )

    def with_resolution_status(
        self, status: DomainResolutionStatus
    ) -> _CanonicalProjectionEnvironment:
        return _CanonicalProjectionEnvironment(
            request=self.request,
            resolution=_make_resolution(
                resolution_id=self.resolution.id, status=status
            ),
            composition=self.composition,
        )


@pytest.fixture
def canonical_projection_fixture() -> _CanonicalProjectionEnvironment:
    return _CanonicalProjectionEnvironment(
        request=_make_request(),
        resolution=_make_resolution(),
        composition=_make_composition(),
    )


class TestAuthorityBinding:
    def test_projection_rejects_non_resolved_authority(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture.with_resolution_status(
            DomainResolutionStatus.BLOCKED
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**env.project_kwargs)

    def test_projection_rejects_blocked_composition(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        conflict = DomainCompositionConflict(
            code="composition:blocked",
            category="policy",
            domains=(DomainId("health"), DomainId("general")),
            severity="high",
            message="blocked for interface projection test",
            blocking=True,
        )
        composition = _make_composition(
            status=DomainCompositionStatus.BLOCKED,
            conflicts=(conflict,),
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            canonical_projection_fixture.integrator.project(
                **{
                    **canonical_projection_fixture.project_kwargs,
                    "composition": composition,
                }
            )

    def test_projection_rejects_mismatched_request_and_resolution(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture.with_request_resolution_reference(
            "resolution:A"
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**env.project_kwargs)

    def test_projection_rejects_mismatched_request_and_composition(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        request = _make_request(composition_reference_id="composition:A")
        with pytest.raises(DomainInterfaceAuthorityError):
            canonical_projection_fixture.integrator.project(
                request=request,
                resolution=canonical_projection_fixture.resolution,
                composition=canonical_projection_fixture.composition,
            )

    def test_projection_rejects_mismatched_resolution_and_composition(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture.with_request_resolution_reference(
            "resolution:A"
        ).with_resolution_id("resolution:B")
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**env.project_kwargs)

    def test_projection_rejects_duck_typed_resolution(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        fake = SimpleNamespace(
            id="resolution:1",
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=DomainId("health"),
            supporting_domains=(DomainId("general"),),
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "resolution": fake})

    def test_projection_rejects_duck_typed_composition(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        fake = SimpleNamespace(
            id="composition:1",
            resolution_id="resolution:1",
            status=DomainCompositionStatus.COMPOSED,
            primary_domain=DomainId("health"),
            supporting_domains=(DomainId("general"),),
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "composition": fake})

    def test_projection_rejects_diverging_primary_domain(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        composition = _make_composition(primary_domain="domain:legal")
        with pytest.raises(DomainInterfaceAuthorityError):
            canonical_projection_fixture.integrator.project(
                **{
                    **canonical_projection_fixture.project_kwargs,
                    "composition": composition,
                }
            )

    def test_projection_rejects_diverging_supporting_domains(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        composition = _make_composition(
            supporting_domains=("domain:general", "domain:legal")
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            canonical_projection_fixture.integrator.project(
                **{
                    **canonical_projection_fixture.project_kwargs,
                    "composition": composition,
                }
            )

    def test_projection_rejects_presentation_bound_to_other_composition(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        presentation = _make_presentation(
            composition_id="composition:other",
            approval_refs=("approval:1",),
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(
                **{**env.project_kwargs, "presentation": presentation}
            )

    def test_projection_rejects_session_reference_mismatch(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        session = DomainSessionContext(
            session_id="session:other",
            primary_domain="domain:health",
            composition_id="composition:1",
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "session": session})

    def test_projection_accepts_coherent_presentation_and_session(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        presentation = _make_presentation(composition_id="composition:1")
        session = DomainSessionContext(
            session_id="session:1",
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            composition_id="composition:1",
        )
        env = canonical_projection_fixture
        projection = env.integrator.project(
            **{
                **env.project_kwargs,
                "presentation": presentation,
                "session": session,
            }
        )
        assert projection.request_id == env.request.request_id

    def test_projection_rejects_session_composition_mismatch(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        session = DomainSessionContext(
            session_id="session:1",
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            composition_id="composition:other",
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "session": session})

    def test_projection_rejects_session_resolution_mismatch(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        session = DomainSessionContext(
            session_id="session:1",
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            composition_id="composition:1",
            last_resolution_id="resolution:other",
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "session": session})

    def test_projection_rejects_session_primary_domain_mismatch(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        session = DomainSessionContext(
            session_id="session:1",
            primary_domain="domain:legal",
            composition_id="composition:1",
            last_resolution_id="resolution:1",
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "session": session})

    def test_projection_rejects_session_supporting_domain_mismatch(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        session = DomainSessionContext(
            session_id="session:1",
            primary_domain="domain:health",
            supporting_domains=("domain:general", "domain:legal"),
            composition_id="composition:1",
            last_resolution_id="resolution:1",
        )
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(**{**env.project_kwargs, "session": session})

    def test_projection_rejects_foreign_memory_knowledge_projection(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        memory_request = _make_memory_knowledge_request()
        foreign_request = _make_memory_knowledge_request(
            request_id="memory-knowledge-request:foreign"
        )
        projection = _make_memory_knowledge_projection(foreign_request)
        env = canonical_projection_fixture
        with pytest.raises(DomainInterfaceAuthorityError):
            env.integrator.project(
                **{
                    **env.project_kwargs,
                    "memory_knowledge": projection,
                    "memory_knowledge_request": memory_request,
                }
            )

    def test_projection_accepts_bound_memory_knowledge_projection(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        memory_request = _make_memory_knowledge_request()
        projection = _make_memory_knowledge_projection(memory_request)
        env = canonical_projection_fixture
        result = env.integrator.project(
            **{
                **env.project_kwargs,
                "memory_knowledge": projection,
                "memory_knowledge_request": memory_request,
            }
        )
        assert result.request_id == env.request.request_id


class TestProjectionPurity:
    def test_projection_is_pure_over_canonical_environment(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        before = env.snapshot_state()
        projection = env.project_interface()
        after = env.snapshot_state()

        assert projection.request_id == env.request.request_id
        assert projection.resolution_reference_id == env.resolution.id
        assert projection.composition_reference_id == env.composition.id
        assert after == before

    def test_projection_content_is_bound_to_canonical_references(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = env.project_interface()

        assert projection.request_id == "interface-request:1"
        assert projection.resolution_reference_id == "resolution:1"
        assert projection.composition_reference_id == "composition:1"


class TestRequestedViewKinds:
    def test_requested_views_accept_each_canonical_kind(self) -> None:
        for kind in DomainInterfaceViewKind:
            request = _make_request(requested_views=(kind,))
            assert request.requested_views == (kind,)


_CONVERSATIONAL = (DomainInterfaceViewKind.CONVERSATIONAL,)
_DOMAIN_CENTER = (DomainInterfaceViewKind.DOMAIN_CENTER,)
_CROSS_DOMAIN = (DomainInterfaceViewKind.CROSS_DOMAIN,)
_REVIEW_CENTER = (DomainInterfaceViewKind.REVIEW_CENTER,)


class TestConversationalProjection:
    def test_conversational_view_preserves_visible_references_and_confidence(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        items = (
            _make_item(
                "knowledge:item:1",
                DomainPresentationItemType.FINDING,
                source_order=0,
                domain_ids=("domain:health",),
                confidence=0.9,
                requires_provenance=True,
            ),
            _make_item(
                "contradiction:1",
                DomainPresentationItemType.CONTRADICTION,
                source_order=1,
                domain_ids=("domain:health",),
            ),
            _make_item(
                "approval:1",
                DomainPresentationItemType.APPROVAL,
                source_order=2,
                domain_ids=("domain:general",),
            ),
        )
        presentation = _make_presentation_with_items(
            items, approval_refs=("approval:1",)
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            presentation=presentation,
        )
        view = projection.conversational
        assert view is not None
        assert view.primary_domain == "domain:health"
        assert view.supporting_domains == ("domain:general",)
        assert view.source_refs == ("knowledge:item:1",)
        assert view.contradiction_refs == ("contradiction:1",)
        assert view.approval_refs == ("approval:1",)
        assert view.workflow_refs == ()
        assert view.question_refs == ()
        assert view.warning_refs == ()
        assert view.memory_proposal_refs == ()
        assert view.result_refs == ()
        assert view.confidence == 0.9
        assert view.status.value == "ready"

    def test_conversational_visibility_denies_hidden_source_and_denied_supporting_domain(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        items = (
            _make_item(
                "knowledge:item:1",
                DomainPresentationItemType.FINDING,
                source_order=0,
                domain_ids=("domain:health",),
                confidence=0.9,
                requires_provenance=True,
            ),
            _make_item(
                "knowledge:item:denied",
                DomainPresentationItemType.FINDING,
                source_order=1,
                domain_ids=("domain:legal",),
                visible=False,
                requires_provenance=True,
            ),
            _make_item(
                "approval:1",
                DomainPresentationItemType.APPROVAL,
                source_order=2,
                domain_ids=("domain:general",),
            ),
        )
        presentation = _make_presentation_with_items(
            items, approval_refs=("approval:1",)
        )
        resolution = _make_resolution(
            supporting_domains=("domain:general", "domain:legal")
        )
        composition = _make_composition(
            supporting_domains=("domain:general", "domain:legal")
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            resolution=resolution,
            composition=composition,
            presentation=presentation,
        )
        view = projection.conversational
        assert view is not None
        assert "knowledge:item:denied" not in view.source_refs
        assert "domain:legal" not in view.supporting_domains
        assert view.source_refs == ("knowledge:item:1",)
        assert view.supporting_domains == ("domain:general",)

    def test_conversational_visibility_hides_items_in_hidden_section(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        items = (
            _make_item(
                "knowledge:item:1",
                DomainPresentationItemType.FINDING,
                source_order=0,
                domain_ids=("domain:health",),
                confidence=0.8,
                requires_provenance=True,
            ),
            _make_item(
                "approval:1",
                DomainPresentationItemType.APPROVAL,
                source_order=1,
                domain_ids=("domain:general",),
            ),
        )
        sections = (
            DomainPresentationSectionPlan(
                section_id="findings",
                item_refs=("knowledge:item:1",),
            ),
            DomainPresentationSectionPlan(
                section_id="restricted",
                item_refs=("approval:1",),
                visible=False,
            ),
        )
        presentation = _make_presentation_with_items(
            items, sections=sections, approval_refs=("approval:1",)
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            presentation=presentation,
        )
        view = projection.conversational
        assert view is not None
        assert view.source_refs == ("knowledge:item:1",)
        assert "approval:1" not in view.approval_refs
        assert view.approval_refs == ()

    def test_conversational_confidence_is_minimum_over_visible_items_only(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        items = (
            _make_item(
                "knowledge:item:a",
                DomainPresentationItemType.FINDING,
                source_order=0,
                domain_ids=("domain:health",),
                confidence=0.9,
                requires_provenance=True,
            ),
            _make_item(
                "knowledge:item:b",
                DomainPresentationItemType.FINDING,
                source_order=1,
                domain_ids=("domain:general",),
                confidence=0.7,
                requires_provenance=True,
            ),
            _make_item(
                "knowledge:item:c",
                DomainPresentationItemType.FINDING,
                source_order=2,
                domain_ids=("domain:legal",),
                confidence=0.3,
                visible=False,
                requires_provenance=True,
            ),
        )
        presentation = _make_presentation_with_items(items)
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            presentation=presentation,
        )
        view = projection.conversational
        assert view is not None
        assert view.confidence == 0.7
        assert "knowledge:item:c" not in view.source_refs
        assert view.source_refs == ("knowledge:item:a", "knowledge:item:b")

    def test_conversational_status_blocks_when_presentation_is_blocked(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        presentation = _make_presentation_with_items(
            (),
            validation_state=DomainPresentationValidationState.BLOCKED,
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            presentation=presentation,
        )
        view = projection.conversational
        assert view is not None
        assert view.status.value == "blocked"

    def test_conversational_status_keeps_partial_composition_partial(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        composition = _make_composition(status=DomainCompositionStatus.PARTIAL)
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            composition=composition,
        )
        view = projection.conversational
        assert view is not None
        assert view.status.value == "partial"

    def test_conversational_without_presentation_surfaces_no_fabricated_refs(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = _project_views(
            env, request=_make_request(requested_views=_CONVERSATIONAL)
        )
        view = projection.conversational
        assert view is not None
        assert view.primary_domain == "domain:health"
        assert view.supporting_domains == ("domain:general",)
        assert view.source_refs == ()
        assert view.contradiction_refs == ()
        assert view.approval_refs == ()
        assert view.workflow_refs == ()
        assert view.question_refs == ()
        assert view.warning_refs == ()
        assert view.memory_proposal_refs == ()
        assert view.result_refs == ()
        assert view.confidence is None
        assert view.status.value == "ready"

    def test_conversational_view_surfaces_canonical_cross_domain_result_ref(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            result_id="cross-domain-result:045",
            composition_id=env.composition.id,
            recommendations=("interface:recommendation:1",),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            cross_domain_result=result,
        )
        view = projection.conversational
        assert view is not None
        assert view.result_refs == ("cross-domain-result:045",)
        assert view.result_refs == (result.id,)


class TestDomainCenterProjection:
    def test_domain_center_active_domain_stays_active(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        registry.register(_make_domain_definition("health"))
        registry.enable("health")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
        )
        view = projection.domain_center
        assert view is not None
        assert len(view.domains) == 1
        entry = view.domains[0]
        assert entry.domain_id == "domain:health"
        assert entry.status == "active"
        assert entry.enabled is True

    def test_domain_center_disabled_domain_stays_disabled(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        registry.register(_make_domain_definition("general"))
        registry.disable("general")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
        )
        view = projection.domain_center
        assert view is not None
        entry = view.domains[0]
        assert entry.domain_id == "domain:general"
        assert entry.status == "disabled"
        assert entry.enabled is False

    def test_domain_center_degraded_domain_stays_degraded(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        registry.register(_make_domain_definition("legal"))
        _mark_degraded(registry, "legal")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
        )
        view = projection.domain_center
        assert view is not None
        entry = view.domains[0]
        assert entry.domain_id == "domain:legal"
        assert entry.status == "degraded"
        assert entry.enabled is True

    def test_domain_center_version_and_refs_come_from_registry_definitions(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        definition = _make_domain_definition(
            "health",
            version="1.2.0",
            capabilities=(
                _make_capability("health", "risk-scoring"),
                _make_capability("health", "care-ops"),
            ),
            operations=("op:assess",),
            workflows=("flow:review",),
            permissions=("perm:read",),
        )
        registry.register(definition)
        registry.enable("health")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
        )
        view = projection.domain_center
        assert view is not None
        entry = view.domains[0]
        assert entry.version == "1.2.0"
        assert entry.capability_refs == ("risk-scoring", "care-ops")
        assert entry.operation_refs == ("op:assess",)
        assert entry.workflow_refs == ("flow:review",)
        assert entry.permission_refs == ("perm:read",)

    def test_domain_center_metrics_and_errors_come_from_observability(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        registry.register(_make_domain_definition("health"))
        registry.enable("health")
        registry.register(_make_domain_definition("general"))
        registry.disable("general")
        generated_at = datetime.now(timezone.utc)
        report = _make_observability_report(
            measurements=(
                DomainMetricMeasurement(
                    name="domains.installed",
                    status=DomainMetricStatus.OBSERVED,
                    unit="count",
                    value=2.0,
                    evidence_reference_ids=(
                        "domain:general",
                        "domain:health",
                        "general",
                        "health",
                    ),
                ),
                DomainMetricMeasurement(
                    name="domains.active",
                    status=DomainMetricStatus.OBSERVED,
                    unit="count",
                    value=1.0,
                    evidence_reference_ids=("health",),
                ),
                DomainMetricMeasurement(
                    name="rules.total",
                    status=DomainMetricStatus.OBSERVED,
                    unit="count",
                    value=0.0,
                    evidence_reference_ids=(),
                ),
            ),
            log_entries=(
                DomainObservabilityLogEntry(
                    source_kind="domain",
                    source_id="domain:health",
                    category="error",
                    status="failed",
                    occurred_at=generated_at,
                    primary_domain="domain:health",
                    reference_ids=("domain:event:health:error:1",),
                ),
                DomainObservabilityLogEntry(
                    source_kind="domain",
                    source_id="domain:general",
                    category="error",
                    status="failed",
                    occurred_at=generated_at,
                    primary_domain="domain:general",
                    reference_ids=("domain:event:general:error:1",),
                ),
                DomainObservabilityLogEntry(
                    source_kind="domain",
                    source_id="domain:health",
                    category="result",
                    status="resolved",
                    occurred_at=generated_at,
                    primary_domain="domain:health",
                    reference_ids=("domain:event:health:result:1",),
                ),
                DomainObservabilityLogEntry(
                    source_kind="domain",
                    source_id="domain:orphan",
                    category="error",
                    status="failed",
                    occurred_at=generated_at,
                    reference_ids=("domain:event:orphan:error:1",),
                ),
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
            observability_report=report,
        )
        view = projection.domain_center
        assert view is not None
        by_id = {entry.domain_id: entry for entry in view.domains}
        health = by_id["domain:health"]
        general = by_id["domain:general"]
        assert health.metric_refs == ("domains.active", "domains.installed")
        assert general.metric_refs == ("domains.installed",)
        assert health.error_refs == ("domain:event:health:error:1",)
        assert general.error_refs == ("domain:event:general:error:1",)
        assert "domain:event:health:result:1" not in health.error_refs
        assert "domain:event:general:error:1" not in health.error_refs
        assert "domain:event:orphan:error:1" not in health.error_refs

    def test_domain_center_update_status_unknown_without_update_authority(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        registry = DomainRegistry()
        registry.register(_make_domain_definition("health"))
        registry.enable("health")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_DOMAIN_CENTER),
            registry=registry,
        )
        view = projection.domain_center
        assert view is not None
        assert view.domains[0].update_status == "unknown"

    def test_domain_center_without_registry_is_not_fabricated(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = _project_views(
            env, request=_make_request(requested_views=_DOMAIN_CENTER)
        )
        assert projection.domain_center is None

    def test_domain_center_rejects_duck_typed_registry(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        fake = SimpleNamespace(list_records=lambda: ())
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=_make_request(requested_views=_DOMAIN_CENTER),
                registry=fake,
            )

    def test_domain_center_rejects_duck_typed_observability_report(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        fake = SimpleNamespace(log_entries=(), metrics=None)
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=_make_request(requested_views=_DOMAIN_CENTER),
                registry=DomainRegistry(),
                observability_report=fake,
            )


class TestCrossDomainProjection:
    def test_cross_domain_transfer_authorization_only_surfaces_safe_reference(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        authorized = _make_transfer(
            source="domain:health",
            target="domain:general",
            identifier="knowledge:item:patient-1",
        )
        private = _make_transfer(
            source="domain:health",
            target="domain:general",
            identifier="knowledge:item:private-1",
            private=True,
        )
        sealed = _make_transfer(
            source="domain:health",
            target="domain:general",
            identifier="knowledge:item:sealed-1",
            transferable=False,
        )
        foreign = _make_transfer(
            source="domain:legal",
            target="domain:general",
            identifier="knowledge:item:foreign-1",
        )
        snapshot = _make_cross_domain_snapshot(
            transfers=(authorized, private, sealed, foreign),
            decisions=(
                _make_decision(
                    "CONTEXT_TRANSFERRED",
                    action="transferred finding knowledge:item:patient-1",
                ),
                _make_decision(
                    "CONTEXT_TRANSFER_BLOCKED",
                    action="transfer blocked for finding knowledge:item:blocked-1",
                ),
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_snapshot=snapshot,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.primary_domain == "domain:health"
        assert view.supporting_domains == ("domain:general",)
        assert view.transfer_refs == ("knowledge:item:patient-1",)
        assert "knowledge:item:private-1" not in view.transfer_refs
        assert "knowledge:item:sealed-1" not in view.transfer_refs
        assert "knowledge:item:foreign-1" not in view.transfer_refs
        assert "knowledge:item:blocked-1" not in view.transfer_refs
        assert view.consolidated_result_ref is None

    def test_cross_domain_result_completed_reports_ready(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            dependencies=(
                _make_dependency(source="domain:health", target="domain:general"),
            ),
            recommendations=("interface:recommendation:1",),
        )
        snapshot = _make_cross_domain_snapshot(
            transfers=(
                _make_transfer(
                    source="domain:health",
                    target="domain:general",
                    identifier="knowledge:item:patient-1",
                ),
            ),
            dependencies=(
                _make_dependency(
                    source="domain:general",
                    target="domain:health",
                    description="live dependency",
                ),
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=result,
            cross_domain_snapshot=snapshot,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.status is DomainInterfaceStatus.READY
        assert view.consolidated_result_ref == result.id
        assert view.transfer_refs == ("knowledge:item:patient-1",)
        # The consolidated result is authoritative for relations when both are
        # provided; the live snapshot never overrides canonical merged state.
        assert view.dependency_refs == ("dependency:health:general:requires",)

    def test_partial_composition_stays_partial(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            recommendations=("interface:recommendation:1",)
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            composition=_make_composition(status=DomainCompositionStatus.PARTIAL),
            cross_domain_result=result,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.status is DomainInterfaceStatus.PARTIAL

    def test_cross_domain_result_blocked_reports_blocked(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            status=CrossDomainStatus.BLOCKED,
            dependencies=(
                _make_dependency(
                    source="domain:health",
                    target="domain:general",
                    blocking=True,
                    satisfied=False,
                ),
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=result,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.status is DomainInterfaceStatus.BLOCKED

    def test_cross_domain_terminal_statuses_fail_closed(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        failed = _make_cross_domain_result(status=CrossDomainStatus.FAILED)
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=failed,
        )
        assert projection.cross_domain is not None
        assert projection.cross_domain.status is DomainInterfaceStatus.BLOCKED

        limited = _make_cross_domain_result(
            status=CrossDomainStatus.LIMIT_REACHED,
            limits=CrossDomainLimits(reached_limits=("iterations",)),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=limited,
        )
        assert projection.cross_domain is not None
        assert projection.cross_domain.status is DomainInterfaceStatus.PARTIAL

        requires_review = _make_cross_domain_result(
            status=CrossDomainStatus.REQUIRES_REVIEW,
            contradictions=(
                _make_contradiction("contradiction:review:1", requires_review=True),
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=requires_review,
        )
        assert projection.cross_domain is not None
        assert projection.cross_domain.status is DomainInterfaceStatus.BLOCKED

    def test_cross_domain_dependency_kinds_preserved_verbatim(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            dependencies=(
                _make_dependency(source="domain:health", target="domain:general"),
                _make_dependency(
                    source="domain:general",
                    target="domain:health",
                    kind="correlation",
                    description="shared correlation",
                ),
            ),
            recommendations=("interface:recommendation:1",),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=result,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.dependency_refs == (
            "dependency:general:health:correlation",
            "dependency:health:general:requires",
        )

    def test_correlation_never_emitted_as_caused_by(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            dependencies=(
                _make_dependency(
                    source="domain:general",
                    target="domain:health",
                    kind="correlation",
                    description="correlated but not caused",
                ),
            ),
            recommendations=("interface:recommendation:1",),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=result,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.dependency_refs == ("dependency:general:health:correlation",)
        assert "caused_by" not in view.dependency_refs[0]
        assert "causes" not in view.dependency_refs[0]

    def test_unresolved_conflict_remains_present(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        result = _make_cross_domain_result(
            contradictions=(
                _make_contradiction("contradiction:unresolved:1"),
                _make_contradiction(
                    "contradiction:resolved:1",
                    resolved=True,
                    resolution="resolved by canonical authority",
                ),
                _make_contradiction(
                    "contradiction:foreign:1",
                    domains=("domain:legal", "domain:general"),
                ),
            ),
            recommendations=("interface:recommendation:1",),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_result=result,
        )
        view = projection.cross_domain
        assert view is not None
        # Unresolved conflicts stay present; resolved and out-of-composition
        # contradictions are never surfaced as live conflicts.
        assert view.conflict_refs == ("contradiction:unresolved:1",)

    def test_cross_domain_snapshot_live_state_reported_pending(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        snapshot = _make_cross_domain_snapshot(
            transfers=(
                _make_transfer(
                    source="domain:health",
                    target="domain:general",
                    identifier="knowledge:item:patient-1",
                ),
            ),
            dependencies=(
                _make_dependency(source="domain:health", target="domain:general"),
            ),
            contradictions=(_make_contradiction("contradiction:snapshot:1"),),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_CROSS_DOMAIN),
            cross_domain_snapshot=snapshot,
        )
        view = projection.cross_domain
        assert view is not None
        assert view.status is DomainInterfaceStatus.PENDING
        assert view.consolidated_result_ref is None
        assert view.transfer_refs == ("knowledge:item:patient-1",)
        assert view.dependency_refs == ("dependency:health:general:requires",)
        assert view.conflict_refs == ("contradiction:snapshot:1",)

    def test_cross_domain_view_not_fabricated_without_canonical_inputs(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = _project_views(
            env, request=_make_request(requested_views=_CROSS_DOMAIN)
        )
        assert projection.cross_domain is None

    def test_cross_domain_rejects_duck_typed_canonical_inputs(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        request = _make_request(requested_views=_CROSS_DOMAIN)
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_result=SimpleNamespace(id="fake"),
            )
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_snapshot=SimpleNamespace(transfers=()),
            )

    def test_cross_domain_rejects_unbound_or_mismatched_composition_binding(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        request = _make_request(requested_views=_CROSS_DOMAIN)
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_result=_make_cross_domain_result(
                    composition_id=None,
                    recommendations=("interface:recommendation:1",),
                ),
            )
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_result=_make_cross_domain_result(
                    composition_id="composition:other",
                    recommendations=("interface:recommendation:1",),
                ),
            )
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_snapshot=_make_cross_domain_snapshot(
                    composition_id=None,
                ),
            )
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                cross_domain_snapshot=_make_cross_domain_snapshot(
                    composition_id="composition:other",
                ),
            )


class TestReviewCenterProjection:
    def test_review_center_projects_pending_operation_approval_with_canonical_ref(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        approval = _make_operation_approval("approval-req:operation:1")
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(approval,),
        )
        view = projection.review_center
        assert view is not None
        assert len(view.items) == 1
        item = view.items[0]
        assert item.review_ref == approval.id
        assert item.state == approval.status.value
        assert item.state == "pending"
        assert item.category == "operation_approval"
        assert item.domain_id == "domain:health"
        assert item.operation_ref == "operation:1"
        assert item.workflow_ref == "workflow:1"
        assert item.reason_ref == "domain_operation.destructive"
        assert item.session_ref is None

    def test_review_center_classifies_cross_domain_access_and_sensitive_persistence(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        cross_access = _make_par(
            action=PermissionCapability.DOMAIN_CROSS_ACCESS,
            requirement_id="permission-requirement:cross:1",
            session_id="session:2",
            domain_id="domain:health",
            target_domain="domain:general",
            operation_id="operation:2",
            workflow_id="workflow:2",
        )
        sensitive = _make_par(
            action=PermissionCapability.SENSITIVE_INFERENCE_PERSIST,
            requirement_id="permission-requirement:sensitive:1",
            session_id="session:3",
            domain_id="domain:general",
            operation_id="operation:3",
        )
        cross_approval = _make_approval(
            approval_id="approval-req:cross:1",
            permission_requirement=cross_access,
            operation_id="operation:2",
            workflow_id="workflow:2",
        )
        sensitive_approval = _make_approval(
            approval_id="approval-req:sensitive:1",
            permission_requirement=sensitive,
            operation_id="operation:3",
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(sensitive_approval, cross_approval),
        )
        view = projection.review_center
        assert view is not None
        assert [item.review_ref for item in view.items] == [
            "approval-req:cross:1",
            "approval-req:sensitive:1",
        ]
        by_ref = {item.review_ref: item for item in view.items}
        cross_item = by_ref["approval-req:cross:1"]
        assert cross_item.category == "cross_domain_access"
        assert cross_item.state == cross_approval.status.value
        assert cross_item.domain_id == "domain:health"
        assert cross_item.operation_ref == "operation:2"
        assert cross_item.workflow_ref == "workflow:2"
        assert cross_item.session_ref == "session:2"
        assert cross_item.reason_ref == "approval_required"
        sensitive_item = by_ref["approval-req:sensitive:1"]
        assert sensitive_item.category == "sensitive_persistence"
        assert sensitive_item.domain_id == "domain:general"
        assert sensitive_item.session_ref == "session:3"
        assert sensitive_item.operation_ref == "operation:3"

    def test_review_center_classifies_external_action_approvals(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        approvals = tuple(
            _make_approval(
                approval_id=f"approval-req:external:{index}",
                permission_requirement=_make_par(
                    action=action,
                    requirement_id=f"permission-requirement:external:{index}",
                    session_id=f"session:{index}",
                ),
            )
            for index, action in enumerate(
                (
                    PermissionCapability.SEARCH_EXTERNAL,
                    PermissionCapability.MODEL_EXTERNAL,
                    PermissionCapability.COMMUNICATION_EXTERNAL,
                )
            )
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=approvals,
        )
        view = projection.review_center
        assert view is not None
        assert len(view.items) == 3
        assert all(item.category == "external_action" for item in view.items)

    def test_review_center_includes_postponed_but_excludes_terminal_approvals(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        postponed = _make_operation_approval(
            "approval-req:operation:postponed:1",
            status=ApprovalRequestStatus.POSTPONED,
            reason_code="domain_operation.approval_required",
        )
        approved = _make_operation_approval(
            "approval-req:operation:approved:1",
            status=ApprovalRequestStatus.APPROVED,
        )
        rejected = _make_operation_approval(
            "approval-req:operation:rejected:1",
            status=ApprovalRequestStatus.REJECTED,
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(approved, rejected, postponed),
        )
        view = projection.review_center
        assert view is not None
        assert len(view.items) == 1
        item = view.items[0]
        assert item.review_ref == "approval-req:operation:postponed:1"
        assert item.state == ApprovalRequestStatus.POSTPONED.value
        assert item.reason_ref == "domain_operation.approval_required"

    def test_review_center_excludes_foreign_domain_approvals(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        foreign = _make_approval(
            approval_id="approval-req:foreign:1",
            permission_requirement=_make_par(
                action=PermissionCapability.DOMAIN_CROSS_ACCESS,
                requirement_id="permission-requirement:foreign:1",
                domain_id="domain:finance",
            ),
        )
        foreign_operation = _make_operation_approval(
            "approval-req:operation:foreign:1",
            primary_domain="domain:finance",
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(foreign_operation, foreign),
        )
        view = projection.review_center
        assert view is not None
        assert view.items == ()

    def test_review_center_excludes_approvals_without_typed_canonical_evidence(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        generic = _make_approval(approval_id="approval-req:generic:1")
        mismatched_scope = _make_operation_approval(
            "approval-req:operation:scope:1",
            metadata_scope="operation",
        )
        missing_domain = _make_approval(
            approval_id="approval-req:operation:unbound:1",
            reason_codes=("domain_operation.destructive",),
            metadata={"scope": "domain_operation"},
        )
        non_review_action = _make_approval(
            approval_id="approval-req:permission:execute:1",
            permission_requirement=_make_par(
                action=PermissionCapability.OPERATION_EXECUTE,
                requirement_id="permission-requirement:execute:1",
            ),
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(generic, mismatched_scope, missing_domain, non_review_action),
        )
        view = projection.review_center
        assert view is not None
        assert view.items == ()

    def test_review_center_projection_does_not_mutate_approval_state(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        approvals = (
            _make_operation_approval("approval-req:operation:1"),
            _make_approval(
                approval_id="approval-req:cross:1",
                permission_requirement=_make_par(
                    action=PermissionCapability.DOMAIN_CROSS_ACCESS,
                    requirement_id="permission-requirement:cross:1",
                ),
            ),
        )
        before = tuple(approval.to_dict() for approval in approvals)
        request = _make_request(requested_views=_REVIEW_CENTER)
        first = _project_views(env, request=request, approvals=approvals)
        assert all(
            approval.status is ApprovalRequestStatus.PENDING for approval in approvals
        )
        assert tuple(approval.to_dict() for approval in approvals) == before
        second = _project_views(env, request=request, approvals=approvals)
        assert second.review_center is not None
        assert first.review_center is not None
        assert second.review_center.to_dict() == first.review_center.to_dict()

    def test_review_center_orders_items_deterministically_by_review_ref(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        approvals = tuple(
            _make_operation_approval(f"approval-req:operation:order:{index}")
            for index in (3, 1, 2)
        )
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=approvals,
        )
        view = projection.review_center
        assert view is not None
        refs = [item.review_ref for item in view.items]
        assert refs == sorted(refs)
        assert refs == [
            "approval-req:operation:order:1",
            "approval-req:operation:order:2",
            "approval-req:operation:order:3",
        ]

    def test_review_center_view_not_fabricated_without_canonical_approvals(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
        )
        assert projection.review_center is None
        empty = _project_views(
            env,
            request=_make_request(requested_views=_REVIEW_CENTER),
            approvals=(),
        )
        assert empty.review_center is not None
        assert empty.review_center.items == ()
        unrequested = _project_views(
            env,
            request=_make_request(requested_views=_CONVERSATIONAL),
            approvals=(_make_operation_approval("approval-req:operation:1"),),
        )
        assert unrequested.review_center is None

    def test_review_center_rejects_duck_typed_or_non_canonical_approvals(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        request = _make_request(requested_views=_REVIEW_CENTER)
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                approvals=(SimpleNamespace(id="fake"),),
            )
        with pytest.raises(DomainInterfaceAuthorityError):
            _project_views(
                env,
                request=request,
                approvals="approval-req:operation:1",
            )


# ── Phase 10.45 selector delegation fixtures ────────────────────────────────

_SELECTOR = (DomainInterfaceViewKind.SELECTOR,)


def _selector_context(
    *,
    explicit: tuple[str, ...] = (),
    authorized: tuple[str, ...] = (),
    available: tuple[str, ...] = ("domain:health", "domain:general"),
    metadata: dict[str, object] | None = None,
) -> DomainResolutionContext:
    """Canonical resolution context over slug references, mirroring resolver tests."""
    return DomainResolutionContext(
        id="ctx:selector:1",
        user_input="selector intent delegation test",
        explicit_domains=tuple(
            DomainId(domain.removeprefix("domain:")) for domain in explicit
        ),
        available_domains=tuple(
            DomainId(domain.removeprefix("domain:")) for domain in available
        ),
        authorized_domains=tuple(
            DomainId(domain.removeprefix("domain:")) for domain in authorized
        ),
        metadata=metadata if metadata is not None else {},
    )


def _selector_intent(
    kind: DomainInterfaceIntentKind,
    *,
    target_domain: str | None = None,
    intent_id: str = "intent:selector:1",
    reason: str | None = None,
    resolution_reference_id: str = "resolution:1",
    composition_reference_id: str = "composition:1",
) -> DomainInterfaceIntent:
    return DomainInterfaceIntent(
        intent_id=intent_id,
        kind=kind,
        resolution_reference_id=resolution_reference_id,
        composition_reference_id=composition_reference_id,
        target_domain=target_domain,
        reason=reason,
    )


def _cross_domain_request(
    *,
    target_domain: str,
    source_domain: str = "domain:health",
    requires_approval: bool = True,
) -> CrossDomainPermissionRequest:
    return CrossDomainPermissionRequest(
        request_id="cross-domain:selector:1",
        source_domain=source_domain,
        target_domain=target_domain,
        reason="selector supporting-domain intent",
        actor_id="actor:selector:1",
        session_id="session:1",
        requires_approval=requires_approval,
        sensitivity_level="internal",
    )


def _register_outbound_policy(
    registry: DomainPermissionRegistry,
    *,
    domain_id: str,
    allowed_target_domains: tuple[str, ...] = ("domain:general",),
) -> None:
    registry.register(
        DomainPermissionPolicy(
            policy_id=f"policy:outbound:{domain_id.removeprefix('domain:')}",
            domain_id=domain_id,
            version="1.0.0",
            allow_cross_domain_access=True,
            allowed_target_domains=allowed_target_domains,
            allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
            allowed_sensitivity_levels=("internal",),
        )
    )


def _register_inbound_policy(
    registry: DomainPermissionRegistry,
    *,
    domain_id: str,
    allowed_source_domains: tuple[str, ...] | None = None,
) -> None:
    policy: dict[str, object] = {
        "policy_id": f"policy:inbound:{domain_id.removeprefix('domain:')}",
        "domain_id": domain_id,
        "version": "1.0.0",
        "allow_inbound_cross_domain_access": True,
        "allowed_sensitivity_levels": ("internal",),
    }
    if allowed_source_domains is not None:
        policy["allowed_source_domains"] = allowed_source_domains
    registry.register(DomainPermissionPolicy(**policy))


class TestSelectorViewProjection:
    def test_selector_view_mirrors_canonical_resolution_selection_state(
        self,
    ) -> None:
        context = _selector_context(
            explicit=("domain:health",),
            authorized=("domain:health", "domain:general"),
        )
        resolved = DefaultDomainResolver().resolve(context)
        assert resolved.status is DomainResolutionStatus.RESOLVED
        assert resolved.primary_domain is not None
        composition = _make_composition(
            composition_id="composition:selector:1",
            resolution_id=resolved.id,
            primary_domain=str(resolved.primary_domain),
            supporting_domains=tuple(str(d) for d in resolved.supporting_domains),
        )
        request = _make_request(
            requested_views=_SELECTOR,
            resolution_reference_id=resolved.id,
            composition_reference_id="composition:selector:1",
        )
        projection = DefaultDomainInterfaceIntegrator().project(
            request=request,
            resolution=resolved,
            composition=composition,
        )
        view = projection.selector
        assert view is not None
        # The selector view copies the canonical selection state verbatim:
        # no relabeling, no domain reordering, no invented rejection reasons.
        assert view.primary_domain == str(resolved.primary_domain)
        assert view.supporting_domains == tuple(
            str(domain) for domain in resolved.supporting_domains
        )
        assert view.rejected_domains == tuple(
            str(domain) for domain in resolved.rejected_domains
        )
        assert view.ambiguous_domains == tuple(
            str(domain) for domain in resolved.ambiguous_domains
        )
        assert view.reason_refs == tuple(
            dict.fromkeys(r.code for r in resolved.reasons)
        )
        assert view.requires_clarification is resolved.requires_clarification
        assert view.status is DomainInterfaceStatus.READY

    def test_selector_view_not_fabricated_when_not_requested(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        projection = _project_views(
            env, request=_make_request(requested_views=_CONVERSATIONAL)
        )
        assert projection.selector is None
        assert projection.conversational is not None


class TestSelectorIntentSubmission:
    def test_auto_resolve_intent_granted_matches_canonical_resolver_authority(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        context = _selector_context(
            explicit=("domain:health",),
            authorized=("domain:health", "domain:general"),
        )
        resolver = DefaultDomainResolver()
        expected = resolver.resolve(context)
        assert expected.status is DomainResolutionStatus.RESOLVED
        assert expected.primary_domain == DomainId("health")
        assert expected.reasons
        integrator = DefaultDomainInterfaceIntegrator(resolver=resolver)
        result = integrator.submit_intent(
            intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=context,
        )
        assert isinstance(result, DomainInterfaceIntentResult)
        assert result.intent_id == "intent:selector:1"
        assert result.accepted is True
        assert result.status is DomainInterfaceStatus.READY
        assert result.resolution_reference_id == env.resolution.id
        assert result.composition_reference_id == env.composition.id
        # The outcome reason comes from the canonical resolver, never from a
        # Phase 10.45 heuristic.
        assert result.reason_code == expected.reasons[0].code

    def test_auto_resolve_intent_pending_when_canonical_ambiguity_requires_clarification(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        context = _selector_context(
            explicit=("domain:health", "domain:general"),
            authorized=("domain:health", "domain:general"),
        )
        resolver = DefaultDomainResolver()
        expected = resolver.resolve(context)
        assert expected.status is DomainResolutionStatus.AMBIGUOUS
        assert expected.requires_clarification is True
        integrator = DefaultDomainInterfaceIntegrator(resolver=resolver)
        result = integrator.submit_intent(
            intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=context,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.PENDING
        assert result.reason_code == expected.reasons[0].code

    def test_select_primary_intent_granted_when_canonical_target_is_selected(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        context = _selector_context(
            explicit=("domain:health",),
            authorized=("domain:health", "domain:general"),
        )
        resolver = DefaultDomainResolver()
        expected = resolver.resolve(context)
        assert expected.status is DomainResolutionStatus.RESOLVED
        assert str(expected.primary_domain) == "domain:health"
        integrator = DefaultDomainInterfaceIntegrator(resolver=resolver)
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.SELECT_PRIMARY,
                target_domain="domain:health",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=context,
        )
        assert result.accepted is True
        assert result.status is DomainInterfaceStatus.READY
        assert result.reason_code == expected.reasons[0].code

    def test_select_primary_intent_rejects_target_not_expressed_by_canonical_context(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """Explicit-domain preference is expressed through canonical contexts only."""
        env = canonical_projection_fixture
        context = _selector_context(
            explicit=("domain:health",),
            authorized=("domain:health", "domain:general"),
        )
        integrator = DefaultDomainInterfaceIntegrator(resolver=DefaultDomainResolver())
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(
                    DomainInterfaceIntentKind.SELECT_PRIMARY,
                    target_domain="domain:general",
                ),
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=context,
            )

    def test_select_primary_intent_pending_when_canonical_authority_ambiguous(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        context = _selector_context(
            explicit=("domain:health", "domain:general"),
            authorized=("domain:health", "domain:general"),
        )
        resolver = DefaultDomainResolver()
        expected = resolver.resolve(context)
        assert expected.status is DomainResolutionStatus.AMBIGUOUS
        integrator = DefaultDomainInterfaceIntegrator(resolver=resolver)
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.SELECT_PRIMARY,
                target_domain="domain:health",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=context,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.PENDING
        assert result.reason_code == expected.reasons[0].code

    def test_add_supporting_intent_denied_matches_canonical_permission_decision(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """A permission-denied supporting domain returns the canonical rejection."""
        env = canonical_projection_fixture
        permission_registry = DomainPermissionRegistry()
        _register_outbound_policy(
            permission_registry,
            domain_id="domain:health",
            allowed_target_domains=("domain:general",),
        )
        permission_resolver = DomainPermissionResolver(permission_registry)
        request = _cross_domain_request(target_domain="domain:general")
        expected = permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.DENY
        assert expected.reasons
        before_resolution = env.resolution.to_dict()
        before_composition = env.composition.to_dict()
        before_policies = permission_registry.snapshot_state()
        integrator = DefaultDomainInterfaceIntegrator(
            permission_resolver=permission_resolver
        )
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                target_domain="domain:general",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
            permission_request=request,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.BLOCKED
        assert result.reason_code == expected.reasons[0]
        # Denied intent leaves composition, resolution and permission state
        # exactly unchanged.
        assert env.resolution.to_dict() == before_resolution
        assert env.composition.to_dict() == before_composition
        assert permission_registry.snapshot_state() == before_policies

    def test_add_supporting_intent_requires_permission_evidence_and_coherence(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        permission_resolver = DomainPermissionResolver(DomainPermissionRegistry())
        integrator = DefaultDomainInterfaceIntegrator(
            permission_resolver=permission_resolver
        )
        intent = _selector_intent(
            DomainInterfaceIntentKind.ADD_SUPPORTING,
            target_domain="domain:general",
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=intent,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
            )
        # Permission evidence must bind to the same target as the intent.
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=intent,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
                permission_request=_cross_domain_request(
                    target_domain="domain:finance"
                ),
            )
        # Permission evidence must originate from the composed primary domain.
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=intent,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
                permission_request=_cross_domain_request(
                    target_domain="domain:general",
                    source_domain="domain:legal",
                ),
            )

    def test_add_supporting_intent_approval_required_reports_pending(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        permission_registry = DomainPermissionRegistry()
        _register_outbound_policy(
            permission_registry,
            domain_id="domain:health",
            allowed_target_domains=("domain:general", "domain:finance"),
        )
        _register_inbound_policy(permission_registry, domain_id="domain:finance")
        permission_resolver = DomainPermissionResolver(permission_registry)
        request = _cross_domain_request(target_domain="domain:finance")
        expected = permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.APPROVAL_REQUIRED
        integrator = DefaultDomainInterfaceIntegrator(
            permission_resolver=permission_resolver
        )
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                target_domain="domain:finance",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
            permission_request=request,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.PENDING
        assert result.reason_code == expected.reasons[0]

    def test_add_supporting_intent_without_coordinator_dependency_stays_unavailable(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """ALLOW eligibility without a wired coordinator: no write seam exists."""
        env = canonical_projection_fixture
        permission_registry = DomainPermissionRegistry()
        _register_outbound_policy(
            permission_registry,
            domain_id="domain:health",
            allowed_target_domains=("domain:general", "domain:finance"),
        )
        _register_inbound_policy(permission_registry, domain_id="domain:finance")
        permission_resolver = DomainPermissionResolver(permission_registry)
        request = _cross_domain_request(
            target_domain="domain:finance",
            requires_approval=False,
        )
        expected = permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.ALLOW
        integrator = DefaultDomainInterfaceIntegrator(
            permission_resolver=permission_resolver
        )
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                target_domain="domain:finance",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
            permission_request=request,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.UNAVAILABLE
        assert (
            result.reason_code == "domain_selector_supporting_application_unavailable"
        )

    def test_privilege_escalation_add_supporting_rejected_without_any_state_change(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """Adding a domain with broader access cannot bypass canonical permission."""
        env = canonical_projection_fixture
        permission_registry = DomainPermissionRegistry()
        _register_outbound_policy(
            permission_registry,
            domain_id="domain:health",
            allowed_target_domains=("domain:general",),
        )
        _register_inbound_policy(
            permission_registry,
            domain_id="domain:finance",
            allowed_source_domains=("domain:health",),
        )
        permission_resolver = DomainPermissionResolver(permission_registry)
        request = _cross_domain_request(target_domain="domain:finance")
        expected = permission_resolver.resolve_cross_domain(request)
        assert expected.decision is PermissionOutcome.DENY
        before_resolution = env.resolution.to_dict()
        before_composition = env.composition.to_dict()
        before_policies = tuple(
            policy.to_dict() for policy in permission_registry.list_policies()
        )
        integrator = DefaultDomainInterfaceIntegrator(
            permission_resolver=permission_resolver
        )
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                target_domain="domain:finance",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
            permission_request=request,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.BLOCKED
        assert result.reason_code == expected.reasons[0]
        # Privilege escalation is denied without permission or autonomy change
        # and without any direct registry/session mutation by Phase 10.45.
        assert env.resolution.to_dict() == before_resolution
        assert env.composition.to_dict() == before_composition
        assert (
            tuple(policy.to_dict() for policy in permission_registry.list_policies())
            == before_policies
        )

    def test_selector_intent_disabled_domain_fails_closed(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """A disabled domain cannot be selected through the canonical resolver."""
        env = canonical_projection_fixture
        registry_versions = {
            "legal": [
                {
                    "version": "1.0.0",
                    "status": DomainStatus.DISABLED.value,
                    "kind": DomainKind.CORE.value,
                },
            ],
        }
        context = _selector_context(
            explicit=("domain:legal",),
            authorized=("domain:legal", "domain:general"),
            available=("domain:legal", "domain:general"),
            metadata={"_resolution_registry_versions": registry_versions},
        )
        resolver = DefaultDomainResolver()
        expected = resolver.resolve(context)
        assert expected.status is DomainResolutionStatus.BLOCKED
        blocking = tuple(reason for reason in expected.reasons if reason.blocking)
        assert blocking
        assert blocking[0].code == "DOMAIN_DISABLED_REJECTED"
        before_resolution = env.resolution.to_dict()
        before_composition = env.composition.to_dict()
        integrator = DefaultDomainInterfaceIntegrator(resolver=resolver)
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.SELECT_PRIMARY,
                target_domain="domain:legal",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=context,
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.BLOCKED
        assert result.reason_code == blocking[0].code
        assert env.resolution.to_dict() == before_resolution
        assert env.composition.to_dict() == before_composition

    def test_withdraw_supporting_intent_without_coordinator_dependency_stays_unavailable(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """Withdrawal without a wired coordinator: no write seam exists."""
        env = canonical_projection_fixture
        integrator = DefaultDomainInterfaceIntegrator()
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.WITHDRAW_SUPPORTING,
                target_domain="domain:general",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.UNAVAILABLE
        assert result.reason_code == "domain_selector_withdrawal_unavailable"

    def test_withdraw_supporting_intent_rejects_unbound_target(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """Without a coordinator, an unbound withdrawal is an incoherent request.

        A wired coordinator is the canonical authority for membership
        preconditions; the interface raises only when no coordinator exists to
        decide them (see the delegation tests below for the typed outcome).
        """
        env = canonical_projection_fixture
        integrator = DefaultDomainInterfaceIntegrator()
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(
                    DomainInterfaceIntentKind.WITHDRAW_SUPPORTING,
                    target_domain="domain:finance",
                ),
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
            )

    def test_explain_selection_intent_read_only_canonical_reason_refs(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        resolution = _make_resolution(
            reasons=(
                DomainResolutionReason(
                    code="DOMAIN_SELECTION_EXPLICIT_PRIORITY",
                    message="explicit preference honored for explain intent",
                    domain_id=DomainId("health"),
                    blocking=False,
                ),
            )
        )
        integrator = DefaultDomainInterfaceIntegrator()
        result = integrator.submit_intent(
            intent=_selector_intent(DomainInterfaceIntentKind.EXPLAIN_SELECTION),
            resolution=resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
        )
        assert result.accepted is True
        assert result.status is DomainInterfaceStatus.READY
        assert result.reason_code == "DOMAIN_SELECTION_EXPLICIT_PRIORITY"
        assert result.resolution_reference_id == resolution.id
        assert result.composition_reference_id == env.composition.id

    def test_request_policy_change_intent_returns_explicit_unsupported_verdict(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        """No authoritative policy-change seam exists in Phase 10.45."""
        env = canonical_projection_fixture
        integrator = DefaultDomainInterfaceIntegrator()
        result = integrator.submit_intent(
            intent=_selector_intent(
                DomainInterfaceIntentKind.REQUEST_POLICY_CHANGE,
                reason="raise the supporting-domain limit",
            ),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(),
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.UNAVAILABLE
        assert (
            result.reason_code
            == "domain_selector_policy_change_requires_later_platform"
        )

    def test_submit_intent_rejects_non_resolved_authority_state(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture.with_resolution_status(
            DomainResolutionStatus.BLOCKED
        )
        integrator = DefaultDomainInterfaceIntegrator(resolver=DefaultDomainResolver())
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
            )

    def test_submit_intent_rejects_unbound_or_duck_typed_canonical_inputs(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        integrator = DefaultDomainInterfaceIntegrator(resolver=DefaultDomainResolver())
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(
                    DomainInterfaceIntentKind.AUTO_RESOLVE,
                    resolution_reference_id="resolution:unbound",
                ),
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=_selector_context(),
            )
        duck_typed = SimpleNamespace(
            id=env.resolution.id,
            status=DomainResolutionStatus.RESOLVED,
            primary_domain=DomainId("health"),
            supporting_domains=(DomainId("general"),),
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
                resolution=duck_typed,
                composition=env.composition,
                resolution_context=_selector_context(),
            )
        diverging = _make_composition(
            supporting_domains=("domain:general", "domain:finance"),
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
                resolution=env.resolution,
                composition=diverging,
                resolution_context=_selector_context(),
            )

    def test_submit_intent_without_delegated_resolver_reports_unavailable(
        self, canonical_projection_fixture: _CanonicalProjectionEnvironment
    ) -> None:
        env = canonical_projection_fixture
        integrator = DefaultDomainInterfaceIntegrator()
        result = integrator.submit_intent(
            intent=_selector_intent(DomainInterfaceIntentKind.AUTO_RESOLVE),
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=_selector_context(
                explicit=("domain:health",),
                authorized=("domain:health", "domain:general"),
            ),
        )
        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.UNAVAILABLE
        assert result.reason_code == "domain_selector_resolver_unavailable"


# ── Phase 10.45 MAJOR-03 selector delegation (canonical coordinator) ────────

_DELEGATION_CLOCK = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)


def _delegation_environment(**overrides: object) -> _CoordinatorEnvironment:
    """Fresh connected canonical environment for delegation tests.

    The environment (and the coordinator fixture module behind it) is imported
    lazily because ``test_domain_selection_transition`` imports shared fixtures
    from this module; a module-level import would cycle during collection.
    """
    from tests.domains.test_domain_selection_transition import (
        _CoordinatorEnvironment,
    )

    return _CoordinatorEnvironment(**overrides)


def _delegation_coordinator(env: _CoordinatorEnvironment) -> DefaultDomainSelectionTransitionCoordinator:
    """Wire the canonical coordinator over the environment's real seams."""
    return DefaultDomainSelectionTransitionCoordinator(
        resolver=env.resolver,
        composer=env.composer,
        domain_registry=env.registry,
        permission_resolver=env.permission_resolver,
        session_adapter=env.adapter,
        clock=lambda: _DELEGATION_CLOCK,
    )


def _delegation_integrator(
    env: _CoordinatorEnvironment,
) -> DefaultDomainInterfaceIntegrator:
    """Interface integrator with the full canonical delegation seam wired."""
    return DefaultDomainInterfaceIntegrator(
        resolver=env.resolver,
        permission_resolver=env.permission_resolver,
        selection_transition_coordinator=_delegation_coordinator(env),
    )


def _delegation_intent(
    env: _CoordinatorEnvironment,
    kind: DomainInterfaceIntentKind,
    *,
    target_domain: str,
    session_reference_id: str | None = None,
) -> DomainInterfaceIntent:
    return DomainInterfaceIntent(
        intent_id="intent:selector:delegation:1",
        kind=kind,
        resolution_reference_id=env.resolution.id,
        composition_reference_id=env.composition.id,
        target_domain=target_domain,
        session_reference_id=session_reference_id,
        reason="user requested a membership change through the domain selector",
    )


def _delegation_permission_request(
    env: _CoordinatorEnvironment,
    *,
    target_domain: str,
    requires_approval: bool = False,
) -> CrossDomainPermissionRequest:
    return CrossDomainPermissionRequest(
        request_id=f"permission:{env.session_id}:selector-delegation",
        source_domain=env.session.primary_domain,
        target_domain=target_domain,
        reason="add a supporting domain through the domain selector",
        actor_id="actor:selector-delegation",
        session_id=env.session_id,
        requires_approval=requires_approval,
        sensitivity_level="internal",
    )


class TestSelectorMembershipIntentDelegation:
    """ADD/WITHDRAW selector intents complete through the canonical coordinator."""

    def _add_submission(self, env: _CoordinatorEnvironment, integrator, *, permission_request, session=None):
        return integrator.submit_intent(
            intent=_delegation_intent(
                env,
                DomainInterfaceIntentKind.ADD_SUPPORTING,
                target_domain=str(DomainId("delta")),
                session_reference_id=session.session_id if session is not None else None,
            ),
            session=session,
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=env.context,
            permission_request=permission_request,
        )

    def test_add_supporting_allowed_intent_completes_through_coordinator(
        self,
    ) -> None:
        env = _delegation_environment()
        permission_request = _delegation_permission_request(
            env, target_domain=str(DomainId("delta"))
        )
        expected = env.permission_resolver.resolve_cross_domain(permission_request)
        assert expected.decision is PermissionOutcome.ALLOW
        before_resolution = env.resolution.to_dict()
        before_composition = env.composition.to_dict()
        before_registry = env.registry_snapshot()
        integrator = _delegation_integrator(env)

        result = self._add_submission(env, integrator, permission_request=permission_request, session=env.session)

        assert result.accepted is True
        assert result.status is DomainInterfaceStatus.READY
        assert result.intent_id == "intent:selector:delegation:1"
        assert result.reason_code == "DOMAIN_SELECTION_REEVALUATED"
        assert result.resolution_reference_id == env.resolution.id
        assert result.composition_reference_id == env.composition.id
        # The delegation never mutates the interface inputs or the registry.
        assert env.resolution.to_dict() == before_resolution
        assert env.composition.to_dict() == before_composition
        assert env.registry_snapshot() == before_registry
        # Exactly one new canonical session revision persists through the
        # shared session store with the delta applied.
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == env.session.revision + 1 == 2
        assert durable.primary_domain == env.session.primary_domain
        assert durable.supporting_domains == (
            str(DomainId("delta")),
            str(DomainId("beta")),
            str(DomainId("gamma")),
        )
        assert len(durable.domain_transitions) == 1
        assert durable.domain_transitions[0].reason_code == "ADD_SUPPORTING"
        assert env.session.revision == 1

    def test_withdraw_supporting_intent_completes_through_coordinator(
        self,
    ) -> None:
        env = _delegation_environment()
        integrator = _delegation_integrator(env)

        result = integrator.submit_intent(
            intent=_delegation_intent(
                env,
                DomainInterfaceIntentKind.WITHDRAW_SUPPORTING,
                target_domain=str(DomainId("beta")),
                session_reference_id=env.session_id,
            ),
            session=env.session,
            resolution=env.resolution,
            composition=env.composition,
            resolution_context=env.context,
        )

        assert result.accepted is True
        assert result.status is DomainInterfaceStatus.READY
        assert result.reason_code == "DOMAIN_SELECTION_REEVALUATED"
        assert result.resolution_reference_id == env.resolution.id
        assert result.composition_reference_id == env.composition.id
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 2
        assert durable.supporting_domains == (str(DomainId("gamma")),)
        assert len(durable.domain_transitions) == 1
        assert durable.domain_transitions[0].reason_code == "WITHDRAW_SUPPORTING"

    def test_add_supporting_deny_verdict_preserved_through_coordinator(
        self,
    ) -> None:
        env = _delegation_environment(outbound_targets=())
        permission_request = _delegation_permission_request(
            env, target_domain=str(DomainId("delta"))
        )
        expected = env.permission_resolver.resolve_cross_domain(permission_request)
        assert expected.decision is PermissionOutcome.DENY
        assert expected.reasons
        integrator = _delegation_integrator(env)

        result = self._add_submission(env, integrator, permission_request=permission_request, session=env.session)

        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.BLOCKED
        assert result.reason_code == expected.reasons[0]
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1
        assert durable.supporting_domains == (
            str(DomainId("beta")),
            str(DomainId("gamma")),
        )

    def test_add_supporting_approval_required_verdict_preserved_through_coordinator(
        self,
    ) -> None:
        env = _delegation_environment()
        permission_request = _delegation_permission_request(
            env,
            target_domain=str(DomainId("delta")),
            requires_approval=True,
        )
        expected = env.permission_resolver.resolve_cross_domain(permission_request)
        assert expected.decision is PermissionOutcome.APPROVAL_REQUIRED
        assert expected.reasons
        integrator = _delegation_integrator(env)

        result = self._add_submission(env, integrator, permission_request=permission_request, session=env.session)

        assert result.accepted is False
        assert result.status is DomainInterfaceStatus.PENDING
        assert result.reason_code == expected.reasons[0]
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_membership_intent_without_session_authority_fails_closed(
        self,
    ) -> None:
        env = _delegation_environment()
        permission_request = _delegation_permission_request(
            env, target_domain=str(DomainId("delta"))
        )
        integrator = _delegation_integrator(env)
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_delegation_intent(
                    env,
                    DomainInterfaceIntentKind.ADD_SUPPORTING,
                    target_domain=str(DomainId("delta")),
                ),
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=env.context,
                permission_request=permission_request,
            )
        duck_typed = SimpleNamespace(
            session_id=env.session_id,
            revision=1,
            primary_domain=env.session.primary_domain,
        )
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_delegation_intent(
                    env,
                    DomainInterfaceIntentKind.ADD_SUPPORTING,
                    target_domain=str(DomainId("delta")),
                ),
                session=duck_typed,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=env.context,
                permission_request=permission_request,
            )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_membership_intent_session_reference_mismatch_fails_closed(
        self,
    ) -> None:
        env = _delegation_environment()
        permission_request = _delegation_permission_request(
            env, target_domain=str(DomainId("delta"))
        )
        integrator = _delegation_integrator(env)
        with pytest.raises(DomainInterfaceAuthorityError):
            integrator.submit_intent(
                intent=_delegation_intent(
                    env,
                    DomainInterfaceIntentKind.ADD_SUPPORTING,
                    target_domain=str(DomainId("delta")),
                    session_reference_id="session:selector:other",
                ),
                session=env.session,
                resolution=env.resolution,
                composition=env.composition,
                resolution_context=env.context,
                permission_request=permission_request,
            )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 1

    def test_stale_session_authority_surfaces_optimistic_conflict(self) -> None:
        env = _delegation_environment()
        permission_request = _delegation_permission_request(
            env, target_domain=str(DomainId("delta"))
        )
        integrator = _delegation_integrator(env)
        first = self._add_submission(env, integrator, permission_request=permission_request, session=env.session)
        assert first.accepted is True
        assert first.status is DomainInterfaceStatus.READY

        # Replaying the same intent with the stale revision-1 authority can no
        # longer commit: the optimistic conflict surfaces as a typed result
        # and the durable revision-2 state is never overwritten.
        second = self._add_submission(env, integrator, permission_request=permission_request, session=env.session)

        assert second.accepted is False
        assert second.status is DomainInterfaceStatus.BLOCKED
        assert (
            second.reason_code
            == "domain_selection_transition_session_conflict"
        )
        durable = env.adapter.load_domain_session(env.session_id)
        assert durable is not None
        assert durable.revision == 2
        assert durable.supporting_domains == (
            str(DomainId("delta")),
            str(DomainId("beta")),
            str(DomainId("gamma")),
        )
