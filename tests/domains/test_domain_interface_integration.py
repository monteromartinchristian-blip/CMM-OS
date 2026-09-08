"""Tests for the Phase 10.45 Domain Interface integration core.

Covers canonical authority binding (fail-closed projection), projection purity,
and the interface views assembled over canonical resolution/composition state.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
)
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainResolutionStatus,
)
from cmm.domains.errors import DomainInterfaceAuthorityError
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceProjectionRequest,
    DomainInterfaceViewKind,
)
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationPlan,
    DomainPresentationSectionPlan,
)
from cmm.domains.registry import DomainRegistry
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
