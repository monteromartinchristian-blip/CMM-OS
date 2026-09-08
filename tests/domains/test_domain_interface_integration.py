"""Tests for the Phase 10.45 Domain Interface integration core.

Covers canonical authority binding (fail-closed projection), projection purity,
and the interface views assembled over canonical resolution/composition state,
presentation visibility, registry lifecycle state and observability authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
)
from cmm.domains.contracts import (
    DomainCapability,
    DomainDefinition,
    DomainMetadata,
)
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainKind,
    DomainResolutionStatus,
    DomainStatus,
)
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceProjectionRequest,
    DomainInterfaceViewKind,
)
from cmm.domains.observability_contracts import (
    DomainMetricMeasurement,
    DomainMetricsSnapshot,
    DomainMetricStatus,
    DomainObservabilityLogEntry,
    DomainObservabilityReport,
)
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
from cmm.domains.resolver_contracts import (
    DomainResolutionReason,
    DomainResolutionResult,
)
from cmm.domains.session_contracts import DomainSessionContext


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
