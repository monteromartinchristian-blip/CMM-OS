"""Tests for Phase 10.44 Domain Memory and Knowledge Graph Integrator."""

from __future__ import annotations

import pytest

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
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemoryTemporalKind,
    DomainMemoryTemporalSnapshot,
    DomainMemoryViewRequest,
)
from cmm.domains.memory_knowledge_integration import (
    DefaultDomainMemoryKnowledgeIntegrator,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver


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
        candidates=references,
        permission_decision_ids=tuple(p.decision_id for p in permission_decisions),
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
        integrator.project(
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
        integrator.project(
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
    projection = integrator.project(
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
    projection = integrator.project(
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
        integrator.project(
            req_unknown_perm,
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
    projection = integrator.project(
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
    projection = integrator.project(
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
    projection = integrator.project(
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
    projection = integrator.project(
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


def test_timeline_ordering_and_unknown_ordering_separation() -> None:
    t1 = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2026-01-01T09:00:00+00:00",
        observed_at="2026-01-01T09:00:00+00:00",
    )
    t2 = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2026-02-01T09:00:00+00:00",
        observed_at="2026-02-01T09:00:00+00:00",
    )
    t_unk = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.UNKNOWN,
    )

    ref_t2 = _make_ref("ref:t2", "item:t2", temporal=t2)
    ref_t1 = _make_ref("ref:t1", "item:t1", temporal=t1)
    ref_unk = _make_ref(
        "ref:unk", "item:unk", temporal=t_unk, has_unknown_ordering=True
    )

    perm = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:all",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:health",
        source_domain_id="domain:health",
    )
    req, mem_req, view, mem_inv, inv = _setup_view_and_request(
        references=(ref_t2, ref_t1, ref_unk),
        permission_decisions=(perm,),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.TIMELINE,
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
    )

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Deterministic chronological timeline ordering
    assert projection.timeline_reference_ids == ("ref:t1", "ref:t2")
    # Unknown ordering collected separately and never assigned a guessed position
    assert projection.unknown_ordering_reference_ids == ("ref:unk",)


def test_timeline_does_not_merge_incompatible_periods() -> None:
    t_old = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2025-01-01T00:00:00+00:00",
        valid_to="2025-06-01T00:00:00+00:00",
    )
    t_new = DomainMemoryTemporalSnapshot(
        kind=DomainMemoryTemporalKind.TIMELESS,
        valid_from="2026-01-01T00:00:00+00:00",
        valid_to="2026-06-01T00:00:00+00:00",
    )
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
    projection = integrator.project(
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # Disjoint intervals are not combined into a synthetic period
    assert projection.timeline_reference_ids == ("ref:old", "ref:new")
    # Verified projection schema contains no synthetic period fields
    assert "combined_period" not in projection.to_dict()
    assert "synthetic_interval" not in projection.to_dict()


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
    projection = integrator.project(
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
    projection = integrator.project(
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
    projection = integrator.project(
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
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:part:2",
        source_id="item:study-goal",
        target_id="item:life-plan",
        kind="part_of",
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
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
    assert path.hops[0].kind == "depends_on"

    assert path.hops[1].relation_id == "rel:part:2"
    assert path.hops[1].source_reference_id == "ref:study-goal"
    assert path.hops[1].target_reference_id == "ref:life-plan"
    assert path.hops[1].kind == "part_of"


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
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    rel_ba = KnowledgeRelation(
        id="rel:ba",
        source_id="item:b",
        target_id="item:a",
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel_ab, rel_ba))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
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
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:part:2",
        source_id="item:study-goal",
        target_id="item:life-plan",
        kind="part_of",
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
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
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:2",
        source_id="item:b",
        target_id="item:c",
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel1, rel2))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
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
        kind="correlated_with",
        confidence=Confidence(value=0.9),
    )
    rel_bc = KnowledgeRelation(
        id="rel:bc",
        source_id="item:b",
        target_id="item:c",
        kind="depends_on",
        confidence=Confidence(value=0.9),
    )
    inv = DomainMemoryKnowledgeInventory(relations=(rel_ab, rel_bc))

    integrator = DefaultDomainMemoryKnowledgeIntegrator()
    projection = integrator.project(
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=inv,
    )

    # correlated_with is not in DEPENDENCY_KINDS -> no dependency path
    assert projection.dependency_paths == ()

    # correlated_with IS in IMPACT_KINDS -> impact path exists
    assert len(projection.impact_paths) == 1
    impact_path = projection.impact_paths[0]
    assert len(impact_path.hops) == 2
    assert impact_path.hops[0].kind == "correlated_with"
    assert impact_path.hops[1].kind == "depends_on"

    # No synthetic direct causal edge emitted
    assert all(
        not (r.source_reference_id == "ref:a" and r.target_reference_id == "ref:c")
        for r in projection.relation_refs
    )
    assert all(r.kind != "caused_by" for r in projection.relation_refs)
    assert all(h.kind != "caused_by" for h in impact_path.hops)
