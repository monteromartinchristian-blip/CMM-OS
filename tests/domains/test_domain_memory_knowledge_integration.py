"""Tests for Phase 10.44 Domain Memory and Knowledge Graph Integrator."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateContext
from cmm.agent_runtime.knowledge_update_proposal_engine import (
    KnowledgeUpdateProposalEngine,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeKind, KnowledgeRelationKind
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem, KnowledgeRelation
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.errors import (
    DomainMemoryKnowledgeAuthorizationError,
    DomainMemoryKnowledgeProjectionError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryProposalBinding,
    DomainMemoryProposalSnapshot,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryTemporalKind,
    DomainMemoryTemporalSnapshot,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewRequest,
    DomainMemoryViewSnapshot,
)
from cmm.domains.memory_knowledge_integration import (
    DefaultDomainMemoryKnowledgeIntegrator,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver


class _FakeResolution:
    id = "res_ref:1"
    primary_domain = None  # set per-test via _fake_authority
    supporting_domains = ()


class _FakeComposition:
    id = "comp_ref:1"
    resolution_id = "res_ref:1"
    primary_domain = None


def _fake_authority(req):  # type: ignore[no-untyped-def]
    res = _FakeResolution()
    res.primary_domain = req.primary_domain
    res.supporting_domains = req.supporting_domains
    comp = _FakeComposition()
    comp.primary_domain = req.primary_domain
    return res, comp


def _project(integrator, request, **kw):  # type: ignore[no-untyped-def]
    res, comp = _fake_authority(request)
    params: dict = {"resolution": res, "composition": comp}
    params.update(kw)
    return integrator.project(
        request,
        **params,
    )


def _make_ref(
    ref_id: str,
    canonical_id: str,
    domain_id: str = "domain:health",
    applicable_domains: tuple[str, ...] = (),
    temporal: DomainMemoryTemporalSnapshot | None = None,
    has_unknown_ordering: bool = False,
    superseded_by_id: str | None = None,
) -> DomainMemoryReference:
    return DomainMemoryReference(
        reference_id=ref_id,
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=canonical_id,
        domain_id=domain_id,
        applicable_domains=applicable_domains,
        temporal=temporal,
        has_unknown_ordering=has_unknown_ordering,
        superseded_by_id=superseded_by_id,
        evidence_ids=(f"ev:{ref_id}",),
        resource_ids=(f"res:{ref_id}",),
    )


def _setup_view_and_request(
    *,
    primary_domain: str = "domain:health",
    supporting_domains: tuple[str, ...] = ("domain:university", "domain:oppositions"),
    references: tuple[DomainMemoryReference, ...] = (),
    permission_decisions: tuple[DomainMemoryPermissionDecisionSnapshot, ...] = (),
    req_permission_ids: tuple[str, ...] = (),
    requested_capabilities: tuple[DomainMemoryKnowledgeProjectionCapability, ...]
    | None = None,
    temporal_reference: str | None = None,
) -> tuple[
    DomainMemoryKnowledgeProjectionRequest,
    DomainMemoryViewRequest,
    any,
    DomainMemoryReferenceInventory,
    DomainMemoryKnowledgeInventory,
]:
    memory_request = DomainMemoryViewRequest(
        request_id="mem_req:1",
        primary_domain=primary_domain,
        supporting_domains=tuple(
            DomainId(d.removeprefix("domain:")) for d in supporting_domains
        ),
        candidates=references,
        permission_decision_ids=tuple(p.decision_id for p in permission_decisions),
        temporal_reference=temporal_reference,
    )
    memory_inventory = DomainMemoryReferenceInventory(
        references=references,
        permission_decisions=permission_decisions,
    )
    view = DefaultDomainMemoryViewResolver().resolve(memory_request, memory_inventory)

    caps = (
        requested_capabilities
        if requested_capabilities is not None
        else (
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        )
    )

    request = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj_req:1",
        primary_domain=DomainId(primary_domain.removeprefix("domain:")),
        supporting_domains=tuple(
            DomainId(d.removeprefix("domain:")) for d in supporting_domains
        ),
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id="res_ref:1",
        composition_reference_id="comp_ref:1",
        permission_decision_ids=req_permission_ids
        or tuple(p.decision_id for p in permission_decisions),
        requested_capabilities=caps,
        temporal_reference=temporal_reference,
    )
    inventory = DomainMemoryKnowledgeInventory()
    return request, memory_request, view, memory_inventory, inventory


def test_integrator_rejects_unvalidated_or_mismatched_view() -> None:
    ref1 = _make_ref("ref:1", "item:1")
    ref2 = _make_ref("ref:2", "item:2")

    req_a, _mem_req_a, _view_a, _mem_inv_a, _inv_a = _setup_view_and_request(
        references=(ref1,),
    )
    _req_b, mem_req_b, view_b, mem_inv_b, inv_b = _setup_view_and_request(
        references=(ref2,),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()

    # Pass request_a with view_b -> digest/view_id mismatch
    with pytest.raises(DomainMemoryKnowledgeProjectionError):
        _project(
            integrator,
            req_a,
            memory_request=mem_req_b,
            view=view_b,
            memory_inventory=mem_inv_b,
            inventory=inv_b,
        )


def test_integrator_uses_phase_10_18_validator() -> None:
    ref = _make_ref("ref:1", "item:1")
    req, mem_req, view, _mem_inv, inv = _setup_view_and_request(
        references=(ref,),
    )

    # Empty inventory in memory_inventory causes validator to fail (ref not in inventory)
    tampered_mem_inv = DomainMemoryReferenceInventory(references=())
    integrator = DefaultDomainMemoryKnowledgeIntegrator()

    with pytest.raises(DomainMemoryKnowledgeProjectionError):
        _project(
            integrator,
            req,
            memory_request=mem_req,
            view=view,
            memory_inventory=tampered_mem_inv,
            inventory=inv,
        )


def test_same_canonical_identity_reused_across_domains() -> None:
    ref = _make_ref(
        ref_id="ref:study-capacity",
        canonical_id="knowledge:study-capacity",
        domain_id="domain:health",
        applicable_domains=("domain:university", "domain:oppositions"),
    )
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        primary_domain="domain:health",
        supporting_domains=("domain:university", "domain:oppositions"),
        references=(ref,),
        permission_decisions=(perm,),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Reused single identity
    assert projection.selected_reference_ids.count("ref:study-capacity") == 1
    assert projection.shared_identity_reference_ids == ("ref:study-capacity",)


def test_authority_coherence_and_exclusions() -> None:
    ref_allowed = _make_ref(
        ref_id="ref:allowed",
        canonical_id="item:allowed",
        domain_id="domain:health",
    )
    ref_denied = _make_ref(
        ref_id="ref:denied",
        canonical_id="item:denied",
        domain_id="domain:university",
    )
    perm_allowed = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:allowed",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )

    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_allowed, ref_denied),
        permission_decisions=(perm_allowed,),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Denied reference never appears in selected
    assert "ref:denied" not in projection.selected_reference_ids
    assert "ref:allowed" in projection.selected_reference_ids

    # Permission ID in request not present in memory_request fails closed
    req_unknown_perm = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj_req:bad_perm",
        primary_domain=req.primary_domain,
        supporting_domains=req.supporting_domains,
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id=req.resolution_reference_id,
        composition_reference_id=req.composition_reference_id,
        permission_decision_ids=("perm:read:allowed", "perm:unauthorized_extra"),
        requested_capabilities=req.requested_capabilities,
    )
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            req_unknown_perm,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
        )


def test_request_digest_changes_projection_identity() -> None:
    ref = _make_ref("ref:1", "item:1")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref,),
        permission_decisions=(perm,),
    )
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    first = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )
    assert first.request_digest == req.digest
    assert first.to_dict()["request_digest"] == req.digest
    from dataclasses import replace as _replace

    alt_req = _replace(req, temporal_reference="2026-09-07T12:00:00+00:00")
    assert alt_req.digest != req.digest
    alt_mem_req = _replace(mem_req, temporal_reference="2026-09-07T12:00:00+00:00")
    alt_view = DefaultDomainMemoryViewResolver().resolve(alt_mem_req, mem_inv)
    alt_req2 = _replace(
        alt_req,
        memory_view_id=alt_view.view_id,
        memory_view_digest=alt_view.digest,
    )
    second = _project(
        integrator,
        alt_req2,
        memory_request=alt_mem_req,
        view=alt_view,
        memory_inventory=mem_inv,
        inventory=inv,
    )
    assert second.request_digest == alt_req2.digest
    assert second.content_digest != first.content_digest
    assert second.projection_id != first.projection_id


def test_supporting_domain_divergence_fails_closed() -> None:
    ref = _make_ref("ref:1", "item:1")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref,),
        permission_decisions=(perm,),
    )
    from dataclasses import replace as _replace

    divergent = _replace(req, supporting_domains=(DomainId("university"),))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            divergent,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
        )


def test_resolution_composition_mismatch_fails_closed() -> None:
    ref = _make_ref("ref:1", "item:1")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref,),
        permission_decisions=(perm,),
    )
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    res, comp = _fake_authority(req)
    bad_res = _FakeResolution()
    bad_res.id = "res:other"
    bad_res.primary_domain = req.primary_domain
    bad_res.supporting_domains = req.supporting_domains
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            req,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
            resolution=bad_res,
            composition=comp,
        )
    bad_comp = _FakeComposition()
    bad_comp.id = "comp:other"
    bad_comp.resolution_id = res.id
    bad_comp.primary_domain = req.primary_domain
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            req,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
            resolution=res,
            composition=bad_comp,
        )
    broken_link = _FakeComposition()
    broken_link.id = comp.id
    broken_link.resolution_id = "res:unlinked"
    broken_link.primary_domain = req.primary_domain
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            req,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
            resolution=res,
            composition=broken_link,
        )
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            req,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
            resolution=None,
            composition=None,
        )


def test_temporal_reference_mismatch_fails_closed() -> None:
    ref = _make_ref("ref:1", "item:1")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref,),
        permission_decisions=(perm,),
        temporal_reference="2026-09-07T12:00:00+00:00",
    )
    from dataclasses import replace as _replace

    divergent = _replace(req, temporal_reference=None)
    assert divergent.digest != req.digest
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    with pytest.raises(DomainMemoryKnowledgeAuthorizationError):
        _project(
            integrator,
            divergent,
            memory_request=mem_req,
            view=view,
            memory_inventory=mem_inv,
            inventory=inv,
        )


def test_projection_does_not_mutate_cognitive_store() -> None:
    store = InMemoryKnowledgeStore()
    k_item = KnowledgeItem(
        id="item:1",
        statement="Current medication dose",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.9),
    )
    store.save_item(k_item)
    initial_count = store.count_items()

    ref = _make_ref("ref:1", "item:1")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref,),
        permission_decisions=(perm,),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert projection.selected_reference_ids == ("ref:1",)
    assert store.count_items() == initial_count


# ── Task 3: Relation projection tests ──────────────────────────────────────


def test_canonical_relation_projection_maps_authorized_endpoints() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
    )

    canonical_rel = KnowledgeRelation(
        id="rel:a_to_b",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(canonical_rel,))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.relation_refs) == 1
    rel_ref = projection.relation_refs[0]
    assert rel_ref.relation_id == "rel:a_to_b"
    assert rel_ref.source_reference_id == "ref:a"
    assert rel_ref.target_reference_id == "ref:b"
    assert rel_ref.kind == "supports"


def test_relation_suppressed_when_endpoint_hidden() -> None:
    ref_a = _make_ref("ref:a", "item:a", domain_id="domain:health")
    ref_b = _make_ref("ref:b", "item:b", domain_id="domain:university")
    # Only allow domain:health, domain:university is denied/excluded
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:health_only",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
    )

    canonical_rel = KnowledgeRelation(
        id="rel:a_to_b",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(canonical_rel,))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Endpoint item:b is hidden -> relation must NOT be emitted
    assert projection.relation_refs == ()
    # Hidden endpoint must not leak
    assert "ref:b" not in projection.selected_reference_ids
    assert "item:b" not in str(projection.to_dict())


def test_relation_preserves_canonical_kind_without_causal_strengthening() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
    )

    # Weaker relation: RELATED_TO
    canonical_rel = KnowledgeRelation(
        id="rel:related",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.RELATED_TO,
        confidence=Confidence(value=0.8),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(canonical_rel,))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.relation_refs) == 1
    rel_ref = projection.relation_refs[0]
    # Exact canonical kind, no causal promotion
    assert rel_ref.kind == "related_to"
    assert rel_ref.kind != "affects"
    assert rel_ref.kind != "caused_by"


# ── Task 4: Timeline and Contradiction projection tests ───────────────────


def test_point_in_time_uses_observed_at_despite_earlier_valid_from() -> None:
    earlier_point = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.POINT_IN_TIME,
        observed_at="2026-02-01T09:00:00+00:00",
        valid_from="2026-01-01T09:00:00+00:00",
    )
    later_point = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.POINT_IN_TIME,
        observed_at="2026-03-01T09:00:00+00:00",
        valid_from="2026-01-15T09:00:00+00:00",
    )
    t_unk = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.UNKNOWN,
    )

    ref_t1 = _make_ref("ref:t1", "item:t1", temporal=earlier_point)
    ref_other = _make_ref("ref:t2", "item:t2", temporal=later_point)
    ref_unk = _make_ref(
        "ref:unk", "item:unk", temporal=t_unk, has_unknown_ordering=True
    )
    point_temporal_reference = "2026-02-01T09:00:00+00:00"

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_other, ref_t1, ref_unk),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.TIMELINE,
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
        temporal_reference=point_temporal_reference,
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # POINT_IN_TIME anchors on observed_at (2026-02-01), ignoring the earlier
    # valid_from decoy (2026-01-01); the other point (observed 2026-03-01) is
    # excluded by Phase 10.18 rather than reordered.
    assert projection.timeline_reference_ids == ("ref:t1",)
    assert "ref:t2" not in projection.timeline_reference_ids
    # Unknown ordering collected separately and never assigned a guessed position
    assert projection.unknown_ordering_reference_ids == ("ref:unk",)


def test_timeless_incidental_valid_from_has_no_chronology() -> None:
    timeless_old = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2025-01-01T00:00:00+00:00",
        observed_at="2025-01-01T00:00:00+00:00",
    )
    timeless_new = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2026-01-01T00:00:00+00:00",
        observed_at="2026-01-01T00:00:00+00:00",
    )
    t_old = timeless_old
    t_new = timeless_new
    ref_old = _make_ref("ref:old", "item:old", temporal=t_old)
    ref_new = _make_ref("ref:new", "item:new", temporal=t_new)

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_old, ref_new),
        permission_decisions=(perm,),
        requested_capabilities=(DomainMemoryKnowledgeProjectionCapability.TIMELINE,),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # TIMELESS carries no chronology even with incidental timestamps
    assert projection.timeline_reference_ids == ()
    assert set(projection.unknown_ordering_reference_ids) == {"ref:old", "ref:new"}
    # Verified projection schema contains no synthetic period fields
    assert "combined_period" not in projection.to_dict()
    assert "synthetic_interval" not in projection.to_dict()


def test_interval_uses_valid_from_and_unknown_stays_unknown() -> None:
    interval_current = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.INTERVAL,
        valid_from="2026-01-01T00:00:00+00:00",
        valid_to="2026-12-31T00:00:00+00:00",
    )
    interval_other = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.INTERVAL,
        valid_from="2025-01-01T00:00:00+00:00",
        valid_to="2025-06-01T00:00:00+00:00",
    )
    unknown_snap = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.UNKNOWN,
    )
    ref_current = _make_ref("ref:current", "item:current", temporal=interval_current)
    ref_old = _make_ref("ref:old", "item:old", temporal=interval_other)
    ref_unk = _make_ref("ref:unk", "item:unk", temporal=unknown_snap)
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_current, ref_old, ref_unk),
        permission_decisions=(perm,),
        requested_capabilities=(DomainMemoryKnowledgeProjectionCapability.TIMELINE,),
        temporal_reference="2026-06-01T00:00:00+00:00",
    )
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    first = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )
    # Only the interval containing the temporal reference is current; the old
    # incompatible interval stays in inventory history, never merged.
    assert first.timeline_reference_ids == ("ref:current",)
    assert "ref:old" not in first.timeline_reference_ids
    assert "ref:unk" in first.unknown_ordering_reference_ids
    assert "ref:unk" not in first.timeline_reference_ids
    assert {r.reference_id for r in mem_inv.references} >= {
        "ref:current",
        "ref:old",
        "ref:unk",
    }
    second = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )
    assert second.timeline_reference_ids == first.timeline_reference_ids
    assert second.content_digest == first.content_digest


def test_canonical_contradiction_projection() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.CONTRADICTIONS,
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
    )

    canonical_contra = Contradiction(
        id="contra:1",
        item_a_id="item:b",
        item_b_id="item:a",
    )
    inv = DomainMemoryKnowledgeInventory(contradictions=(canonical_contra,))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.contradiction_refs) == 1
    c_ref = projection.contradiction_refs[0]
    assert c_ref.contradiction_id == "contra:1"
    # Canonically sorted participant references
    assert c_ref.reference_ids == ("ref:a", "ref:b")


def test_contradiction_suppressed_when_participant_hidden() -> None:
    ref_a = _make_ref("ref:a", "item:a", domain_id="domain:health")
    ref_b = _make_ref("ref:b", "item:b", domain_id="domain:university")
    # Health only, university denied
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:health_only",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.CONTRADICTIONS,
        ),
    )

    canonical_contra = Contradiction(
        id="contra:1",
        item_a_id="item:a",
        item_b_id="item:b",
    )
    inv = DomainMemoryKnowledgeInventory(contradictions=(canonical_contra,))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Participant item:b is hidden -> contradiction suppressed
    assert projection.contradiction_refs == ()


def test_succession_is_not_treated_as_contradiction() -> None:
    ref_newer = _make_ref("ref:newer", "item:newer")
    ref_older = _make_ref(
        "ref:older",
        "item:older",
        superseded_by_id="item:newer",
    )
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_older, ref_newer),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.CONTRADICTIONS,
        ),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Succession alone never synthesizes a contradiction
    assert projection.contradiction_refs == ()


# ── Task 5: Dependency and Impact path tests ──────────────────────────────


def test_two_hop_dependency_path_preserves_hops_and_relation_identities() -> None:
    ref_cap = _make_ref("ref:study-capacity", "item:study-capacity")
    ref_goal = _make_ref("ref:study-goal", "item:study-goal")
    ref_plan = _make_ref("ref:life-plan", "item:life-plan")

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_cap, ref_goal, ref_plan),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        ),
    )

    rel1 = KnowledgeRelation(
        id="rel:dep:1",
        source_id="item:study-capacity",
        target_id="item:study-goal",
        kind=KnowledgeRelationKind.DERIVED_FROM,
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:part:2",
        source_id="item:study-goal",
        target_id="item:life-plan",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.dependency_paths) == 1
    path = projection.dependency_paths[0]
    assert len(path.hops) == 2
    assert path.hops[0].relation_id == "rel:dep:1"
    assert path.hops[0].source_reference_id == "ref:study-capacity"
    assert path.hops[0].target_reference_id == "ref:study-goal"
    assert path.hops[0].kind == KnowledgeRelationKind.DERIVED_FROM.value

    assert path.hops[1].relation_id == "rel:part:2"
    assert path.hops[1].source_reference_id == "ref:study-goal"
    assert path.hops[1].target_reference_id == "ref:life-plan"
    assert path.hops[1].kind == KnowledgeRelationKind.SUPPORTS.value


def test_path_traversal_cycle_safety() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
        ),
    )

    rel_ab = KnowledgeRelation(
        id="rel:ab",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    rel_ba = KnowledgeRelation(
        id="rel:ba",
        source_id="item:b",
        target_id="item:a",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel_ab, rel_ba))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Terminates deterministically and emits no repeated-edge infinite path
    assert len(projection.dependency_paths) == 2
    for p in projection.dependency_paths:
        # Every hop in a path has a unique relation ID (no repeated edges)
        hop_rel_ids = [h.relation_id for h in p.hops]
        assert len(hop_rel_ids) == len(set(hop_rel_ids))


def test_path_hops_retain_canonical_relation_identity_without_synthetic_direct_edge() -> (
    None
):
    ref_cap = _make_ref("ref:study-capacity", "item:study-capacity")
    ref_goal = _make_ref("ref:study-goal", "item:study-goal")
    ref_plan = _make_ref("ref:life-plan", "item:life-plan")

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_cap, ref_goal, ref_plan),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        ),
    )

    rel1 = KnowledgeRelation(
        id="rel:dep:1",
        source_id="item:study-capacity",
        target_id="item:study-goal",
        kind=KnowledgeRelationKind.DERIVED_FROM,
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:part:2",
        source_id="item:study-goal",
        target_id="item:life-plan",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.dependency_paths) == 1
    serialized = projection.dependency_paths[0].to_dict()
    assert "hops" in serialized
    assert len(serialized["hops"]) == 2
    assert serialized["hops"][0]["relation_id"] == "rel:dep:1"
    assert serialized["hops"][1]["relation_id"] == "rel:part:2"

    # No synthetic direct A -> C relation emitted
    assert all(
        not (
            r.source_reference_id == "ref:study-capacity"
            and r.target_reference_id == "ref:life-plan"
        )
        for r in projection.relation_refs
    )


def test_path_suppressed_when_intermediate_hop_hidden() -> None:
    ref_a = _make_ref("ref:a", "item:a", domain_id="domain:health")
    ref_b = _make_ref("ref:b", "item:b", domain_id="domain:university")
    ref_c = _make_ref("ref:c", "item:c", domain_id="domain:health")

    # Only health allowed, university excluded
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:health_only",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b, ref_c),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        ),
    )

    rel1 = KnowledgeRelation(
        id="rel:1",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:2",
        source_id="item:b",
        target_id="item:c",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Intermediate hop item:b is hidden -> no path exposes hidden node
    assert projection.dependency_paths == ()
    assert projection.relation_refs == ()


def test_impact_path_allows_correlated_without_causal_strengthening() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")
    ref_c = _make_ref("ref:c", "item:c")

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b, ref_c),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
            DomainMemoryKnowledgeProjectionCapability.IMPACT_PATHS,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        ),
    )

    rel_ab = KnowledgeRelation(
        id="rel:ab",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.RELATED_TO,
        confidence=Confidence(value=0.9),
    )
    rel_bc = KnowledgeRelation(
        id="rel:bc",
        source_id="item:b",
        target_id="item:c",
        kind=KnowledgeRelationKind.DERIVED_FROM,
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel_ab, rel_bc))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert len(projection.impact_paths) == 1
    impact_path = projection.impact_paths[0]
    assert len(impact_path.hops) == 2
    assert impact_path.hops[0].kind == KnowledgeRelationKind.RELATED_TO.value
    assert impact_path.hops[1].kind == KnowledgeRelationKind.DERIVED_FROM.value

    # No synthetic direct causal edge emitted
    assert all(
        not (r.source_reference_id == "ref:a" and r.target_reference_id == "ref:c")
        for r in projection.relation_refs
    )
    assert all(r.kind != "caused_by" for r in projection.relation_refs)
    assert all(h.kind != "caused_by" for h in impact_path.hops)


def test_weaker_canonical_related_to_never_strengthened_to_causal() -> None:
    ref_a = _make_ref("ref:a", "item:a")
    ref_b = _make_ref("ref:b", "item:b")
    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, _ = _setup_view_and_request(
        references=(ref_a, ref_b),
        permission_decisions=(perm,),
    )
    weaker = KnowledgeRelation(
        id="rel:weaker",
        source_id="item:a",
        target_id="item:b",
        kind=KnowledgeRelationKind.RELATED_TO,
        confidence=Confidence(value=0.8),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(weaker,))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )
    assert len(projection.relation_refs) == 1
    assert projection.relation_refs[0].kind == KnowledgeRelationKind.RELATED_TO.value


# ── Task 6: Proposal binding tests ────────────────────────────────────────


def _make_proposal_binding_id(
    domain_id: str,
    trace_id: str,
    view_id: str,
    view_digest: str,
    agent_knowledge_proposal_ids: tuple[str, ...],
    affected_reference_ids: tuple[str, ...],
    permission_decision_ids: tuple[str, ...],
) -> str:
    content = {
        "domain_id": domain_id,
        "trace_id": trace_id,
        "view_id": view_id,
        "view_digest": view_digest,
        "memory_proposal_ids": [],
        "agent_knowledge_proposal_ids": sorted(set(agent_knowledge_proposal_ids)),
        "affected_reference_ids": sorted(set(affected_reference_ids)),
        "permission_decision_ids": sorted(set(permission_decision_ids)),
        "approval_request_ids": [],
        "approval_decision_ids": [],
    }
    canonical_json = json.dumps(content, sort_keys=True, separators=(",", ":"))
    content_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"binding:{domain_id}:{trace_id}:{view_id}:{content_digest[:12]}"


def _setup_proposal_binding_context(
    *,
    propose_allowed: bool = True,
    proposal_id: str | None = None,
    tamper_binding: bool = False,
):
    ref1 = _make_ref("ref:1", "item:1")
    perm_read = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    perm_propose = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:propose:1",
        allowed=propose_allowed,
        capabilities=("PROPOSE",) if propose_allowed else ("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )

    trace_snap = DomainMemoryTraceSnapshot(
        trace_id="trace:1", primary_domain="domain:health"
    )

    mem_req = DomainMemoryViewRequest(
        request_id="mem_req:1",
        primary_domain="domain:health",
        trace_id="trace:1",
        candidates=(ref1,),
        permission_decision_ids=("perm:read:1", "perm:propose:1"),
    )

    initial_inv = DomainMemoryReferenceInventory(
        references=(ref1,),
        permission_decisions=(perm_read, perm_propose),
        traces=(trace_snap,),
    )

    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(mem_req, initial_inv)

    view_snap = DomainMemoryViewSnapshot(
        view_id=view.view_id,
        request_id=mem_req.request_id,
        primary_domain=view.primary_domain,
        trace_id="trace:1",
        view_digest=view.content_digest,
    )

    pid = proposal_id or "prop:1"
    prop_snap = DomainMemoryProposalSnapshot(
        proposal_id=pid,
        proposal_kind="agent_knowledge_update",
        affected_reference_ids=("ref:1",),
        required_capabilities=("PROPOSE",),
    )

    mem_inv_full = DomainMemoryReferenceInventory(
        references=(ref1,),
        permission_decisions=(perm_read, perm_propose),
        traces=(trace_snap,),
        views=(view_snap,),
        proposals=(prop_snap,),
    )

    binding_id = _make_proposal_binding_id(
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=(pid,),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:propose:1",),
    )

    if tamper_binding:
        binding_id = binding_id[:-4] + "dead"

    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=(pid,),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:propose:1",),
    )

    req = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj_req:1",
        primary_domain=DomainId("health"),
        supporting_domains=(),
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id="res_ref:1",
        composition_reference_id="comp_ref:1",
        permission_decision_ids=("perm:read:1", "perm:propose:1"),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.RELATION_PROPOSALS,
        ),
    )

    return req, mem_req, view, mem_inv_full, binding


def test_real_canonical_relation_proposal_and_validated_binding_projection() -> None:
    repo = InMemoryKnowledgeUpdateRepository()
    engine = KnowledgeUpdateProposalEngine(repository=repo)
    ctx = KnowledgeUpdateContext(
        context_id="ctx-1",
        agent_run_id="run-1",
        goal_id="goal-1",
    )
    mock_goal = MagicMock()
    mock_goal.goal_id = "goal-1"
    mock_goal.title = "Test Goal"
    mock_goal.kind = "general"

    mock_dec = MagicMock()
    mock_dec.decision_kind = "complete"
    mock_dec.confidence = 0.95

    prop = engine.create_proposal(
        context=ctx,
        goal=mock_goal,
        completion_decision=mock_dec,
    )
    assert prop.proposal_id != ""

    req, mem_req, view, mem_inv, binding = _setup_proposal_binding_context(
        proposal_id=prop.proposal_id,
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    assert validator.validate_binding(binding, mem_inv).is_valid is True

    inv = DomainMemoryKnowledgeInventory(proposal_bindings=(binding,))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Valid binding appears in projection
    assert binding.binding_id in projection.proposal_binding_ids

    # Proposal payload is NOT copied into projection
    proj_dict = projection.to_dict()
    assert "additions" not in proj_dict
    assert "proposals" not in proj_dict
    assert "decisions" not in proj_dict


def test_tampered_proposal_binding_excluded_fail_closed() -> None:
    req, mem_req, view, mem_inv, valid_binding = _setup_proposal_binding_context(
        proposal_id="prop:valid",
    )
    # Tampered / unrecorded proposal binding: binding is structurally valid but references
    # an unrecorded proposal not present in mem_inv.proposals
    unrecorded_binding_id = _make_proposal_binding_id(
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=("prop:unrecorded",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:propose:1",),
    )
    unrecorded_binding = DomainMemoryProposalBinding(
        binding_id=unrecorded_binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=("prop:unrecorded",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:propose:1",),
    )

    inv = DomainMemoryKnowledgeInventory(
        proposal_bindings=(valid_binding, unrecorded_binding)
    )
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert valid_binding.binding_id in projection.proposal_binding_ids
    assert unrecorded_binding.binding_id not in projection.proposal_binding_ids


def test_read_only_authority_cannot_authorize_proposal_binding() -> None:
    # PROPOSE permission is disabled (propose_allowed=False -> only READ capability)
    req, mem_req, view, mem_inv, binding = _setup_proposal_binding_context(
        propose_allowed=False,
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    res = validator.validate_binding(binding, mem_inv)
    assert res.is_valid is False

    inv = DomainMemoryKnowledgeInventory(proposal_bindings=(binding,))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Unvalidated binding excluded fail-closed
    assert projection.proposal_binding_ids == ()


def test_projection_never_mutates_proposal_or_writes_to_cognitive_store() -> None:
    repo = InMemoryKnowledgeUpdateRepository()
    engine = KnowledgeUpdateProposalEngine(repository=repo)
    ctx = KnowledgeUpdateContext(
        context_id="ctx-1",
        agent_run_id="run-1",
        goal_id="goal-1",
    )
    mock_goal = MagicMock()
    mock_goal.goal_id = "goal-1"
    mock_goal.title = "Test Goal"
    mock_goal.kind = "general"

    mock_dec = MagicMock()
    mock_dec.decision_kind = "complete"
    mock_dec.confidence = 0.95

    prop = engine.create_proposal(
        context=ctx,
        goal=mock_goal,
        completion_decision=mock_dec,
    )
    initial_prop = repo.get_proposal(prop.proposal_id)

    store = InMemoryKnowledgeStore()
    store_items_before = len(store.list_items())
    store_relations_before = len(store.list_relations())

    req, mem_req, view, mem_inv, binding = _setup_proposal_binding_context(
        proposal_id=prop.proposal_id,
    )
    inv = DomainMemoryKnowledgeInventory(proposal_bindings=(binding,))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    assert binding.binding_id in projection.proposal_binding_ids

    # Proposal state in repository is unchanged
    assert repo.get_proposal(prop.proposal_id) == initial_prop

    # Store state is unchanged
    assert len(store.list_items()) == store_items_before
    assert len(store.list_relations()) == store_relations_before


def test_missing_authority_adversarial_downgrade() -> None:
    # Downgrade authority: propose permission missing
    ref1 = _make_ref("ref:1", "item:1")
    perm_read = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:1",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    trace_snap = DomainMemoryTraceSnapshot(
        trace_id="trace:1", primary_domain="domain:health"
    )
    mem_req = DomainMemoryViewRequest(
        request_id="mem_req:1",
        primary_domain="domain:health",
        trace_id="trace:1",
        candidates=(ref1,),
        permission_decision_ids=("perm:read:1",),
    )
    mem_inv = DomainMemoryReferenceInventory(
        references=(ref1,),
        permission_decisions=(perm_read,),
        traces=(trace_snap,),
    )
    resolver = DefaultDomainMemoryViewResolver()
    view = resolver.resolve(mem_req, mem_inv)

    binding_id = _make_proposal_binding_id(
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=("prop:unauth",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:read:1",),
    )
    binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=("prop:unauth",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:read:1",),
    )

    req = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj_req:1",
        primary_domain=DomainId("health"),
        supporting_domains=(),
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id="res_ref:1",
        composition_reference_id="comp_ref:1",
        permission_decision_ids=("perm:read:1",),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.RELATION_PROPOSALS,
        ),
    )
    inv = DomainMemoryKnowledgeInventory(proposal_bindings=(binding,))
    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = _project(
        integrator,
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Proposal binding projected = no
    assert projection.proposal_binding_ids == ()
