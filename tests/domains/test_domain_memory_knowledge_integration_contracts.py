"""Tests for Phase 10.44 Domain Memory and Knowledge Graph Integration Contracts."""

from __future__ import annotations

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeRelationKind
from cmm.cognitive.knowledge import Contradiction, KnowledgeRelation
from cmm.domains.errors import (
    DomainMemoryKnowledgeContractError,
    DomainMemoryKnowledgeSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    DomainMemoryProposalBinding,
    _sha256_digest,
)
from cmm.domains.memory_knowledge_integration_contracts import (
    DomainMemoryKnowledgeContradictionRef,
    DomainMemoryKnowledgeIntegrator,
    DomainMemoryKnowledgeInventory,
    DomainMemoryKnowledgePath,
    DomainMemoryKnowledgePathHop,
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
    DomainMemoryKnowledgeRelationRef,
)


def _sample_binding() -> DomainMemoryProposalBinding:
    v_digest = "a" * 64
    v_id = f"view:health:{v_digest[:12]}"
    content_digest = _sha256_digest(
        {
            "domain_id": "domain:health",
            "trace_id": "trace:1",
            "view_id": v_id,
            "view_digest": v_digest,
            "memory_proposal_ids": ["prop:mem:1"],
            "agent_knowledge_proposal_ids": [],
            "affected_reference_ids": ["ref:1"],
            "permission_decision_ids": ["perm:1"],
            "approval_request_ids": [],
            "approval_decision_ids": [],
        }
    )
    b_id = f"binding:domain:health:trace:1:{v_id}:{content_digest[:12]}"
    return DomainMemoryProposalBinding(
        binding_id=b_id,
        domain_id="domain:health",
        trace_id="trace:1",
        view_id=v_id,
        view_digest=v_digest,
        memory_proposal_ids=("prop:mem:1",),
        affected_reference_ids=("ref:1",),
        permission_decision_ids=("perm:1",),
    )


# ── Capability Enum ─────────────────────────────────────────────────────────


def test_projection_capability_values_are_closed_and_stable() -> None:
    assert {item.value for item in DomainMemoryKnowledgeProjectionCapability} == {
        "shared_identities",
        "relations",
        "timeline",
        "contradictions",
        "dependencies",
        "impact_paths",
        "relation_proposals",
    }


# ── RelationRef ─────────────────────────────────────────────────────────────


def test_relation_ref_valid() -> None:
    ref = DomainMemoryKnowledgeRelationRef(
        relation_id="rel:1",
        source_reference_id="ref:a",
        target_reference_id="ref:b",
        kind="supports",
        provenance_reference="prov:1",
    )
    assert ref.relation_id == "rel:1"
    assert ref.source_reference_id == "ref:a"
    assert ref.target_reference_id == "ref:b"
    assert ref.kind == "supports"
    assert ref.provenance_reference == "prov:1"


def test_relation_ref_rejects_blank_ids() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="   ",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind="supports",
        )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="rel:1",
            source_reference_id="",
            target_reference_id="ref:b",
            kind="supports",
        )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="rel:1",
            source_reference_id="ref:a",
            target_reference_id=" ",
            kind="supports",
        )


def test_relation_ref_rejects_self_edge() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="rel:1",
            source_reference_id="ref:1",
            target_reference_id="ref:1",
            kind="supports",
        )


@pytest.mark.parametrize(
    "bad_kind",
    ["depends_on", "part_of", "blocks", "enables", "correlated_with", "caused_by", ""],
)
def test_relation_ref_rejects_noncanonical_kind(bad_kind: str) -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="rel:1",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind=bad_kind,
        )


@pytest.mark.parametrize(
    "bad_kind",
    ["depends_on", "part_of", "correlated_with", "caused_by"],
)
def test_path_hop_rejects_noncanonical_kind(bad_kind: str) -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePathHop(
            relation_id="rel:1",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind=bad_kind,
        )


def test_relation_ref_rejects_empty_kind() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeRelationRef(
            relation_id="rel:1",
            source_reference_id="ref:a",
            target_reference_id="ref:b",
            kind="  ",
        )


def test_relation_ref_serialization_round_trip() -> None:
    ref = DomainMemoryKnowledgeRelationRef(
        relation_id="rel:1",
        source_reference_id="ref:a",
        target_reference_id="ref:b",
        kind="supports",
        provenance_reference="prov:1",
    )
    data = ref.to_dict()
    assert data == {
        "relation_id": "rel:1",
        "source_reference_id": "ref:a",
        "target_reference_id": "ref:b",
        "kind": "supports",
        "provenance_reference": "prov:1",
    }
    restored = DomainMemoryKnowledgeRelationRef.from_dict(data)
    assert restored == ref


def test_relation_ref_rejects_unknown_fields() -> None:
    data = {
        "relation_id": "rel:1",
        "source_reference_id": "ref:a",
        "target_reference_id": "ref:b",
        "kind": "supports",
        "unknown_extra": "foo",
    }
    with pytest.raises(DomainMemoryKnowledgeSerializationError):
        DomainMemoryKnowledgeRelationRef.from_dict(data)


# ── ContradictionRef ────────────────────────────────────────────────────────


def test_contradiction_ref_valid_and_sorted() -> None:
    ref = DomainMemoryKnowledgeContradictionRef(
        contradiction_id="contra:1",
        reference_ids=("ref:z", "ref:a"),
        resolution_reference_id="res:1",
    )
    assert ref.contradiction_id == "contra:1"
    # canonically sorted
    assert ref.reference_ids == ("ref:a", "ref:z")
    assert ref.resolution_reference_id == "res:1"


def test_contradiction_ref_rejects_single_or_empty_references() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeContradictionRef(
            contradiction_id="contra:1",
            reference_ids=(),
        )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeContradictionRef(
            contradiction_id="contra:1",
            reference_ids=("ref:a",),
        )


def test_contradiction_ref_rejects_duplicate_references() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeContradictionRef(
            contradiction_id="contra:1",
            reference_ids=("ref:a", "ref:a"),
        )


def test_contradiction_ref_rejects_blank_ids() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeContradictionRef(
            contradiction_id="  ",
            reference_ids=("ref:a", "ref:b"),
        )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeContradictionRef(
            contradiction_id="contra:1",
            reference_ids=("ref:a", ""),
        )


def test_contradiction_ref_serialization_round_trip() -> None:
    ref = DomainMemoryKnowledgeContradictionRef(
        contradiction_id="contra:1",
        reference_ids=("ref:b", "ref:a"),
        resolution_reference_id=None,
    )
    data = ref.to_dict()
    assert data == {
        "contradiction_id": "contra:1",
        "reference_ids": ["ref:a", "ref:b"],
        "resolution_reference_id": None,
    }
    restored = DomainMemoryKnowledgeContradictionRef.from_dict(data)
    assert restored == ref


def test_contradiction_ref_rejects_unknown_fields() -> None:
    data = {
        "contradiction_id": "contra:1",
        "reference_ids": ["ref:a", "ref:b"],
        "raw_statement": "should fail",
    }
    with pytest.raises(DomainMemoryKnowledgeSerializationError):
        DomainMemoryKnowledgeContradictionRef.from_dict(data)


# ── PathHop & Path ──────────────────────────────────────────────────────────


def test_path_hop_valid_and_rejects_self_edge() -> None:
    hop = DomainMemoryKnowledgePathHop(
        relation_id="rel:1",
        source_reference_id="ref:a",
        target_reference_id="ref:b",
        kind="supports",
    )
    assert hop.relation_id == "rel:1"
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePathHop(
            relation_id="rel:1",
            source_reference_id="ref:a",
            target_reference_id="ref:a",
            kind="supports",
        )


def test_path_id_is_bound_to_ordered_hop_content() -> None:
    hop1 = DomainMemoryKnowledgePathHop("rel:a", "ref:a", "ref:b", "supports")
    hop2 = DomainMemoryKnowledgePathHop("rel:b", "ref:b", "ref:c", "derived_from")
    path1 = DomainMemoryKnowledgePath.create((hop1, hop2))

    assert path1.hops == (hop1, hop2)
    assert len(path1.content_digest) == 64
    assert path1.path_id == f"domain-memory-knowledge-path:{path1.content_digest[:16]}"

    # Reverse hops (if connected, e.g. ref:c -> ref:b -> ref:a) produces different digest
    hop2_rev = DomainMemoryKnowledgePathHop("rel:b", "ref:c", "ref:b", "derived_from")
    hop1_rev = DomainMemoryKnowledgePathHop("rel:a", "ref:b", "ref:a", "supports")
    path2 = DomainMemoryKnowledgePath.create((hop2_rev, hop1_rev))

    assert path1.content_digest != path2.content_digest
    assert path1.path_id != path2.path_id


def test_path_rejects_empty_hops() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePath.create(())


def test_path_rejects_disconnected_hops() -> None:
    hop1 = DomainMemoryKnowledgePathHop("rel:a", "ref:a", "ref:b", "supports")
    hop2 = DomainMemoryKnowledgePathHop("rel:b", "ref:x", "ref:c", "derived_from")
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePath.create((hop1, hop2))


def test_path_rejects_tampered_id_or_digest() -> None:
    hop = DomainMemoryKnowledgePathHop("rel:a", "ref:a", "ref:b", "supports")
    valid_path = DomainMemoryKnowledgePath.create((hop,))
    # Tamper with content_digest
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePath(
            path_id=valid_path.path_id,
            hops=(hop,),
            content_digest="0" * 64,
        )
    # Tamper with path_id
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgePath(
            path_id="domain-memory-knowledge-path:tampered1234567",
            hops=(hop,),
            content_digest=valid_path.content_digest,
        )


def test_path_serialization_round_trip() -> None:
    hop = DomainMemoryKnowledgePathHop("rel:a", "ref:a", "ref:b", "supports")
    path = DomainMemoryKnowledgePath.create((hop,))
    data = path.to_dict()
    restored = DomainMemoryKnowledgePath.from_dict(data)
    assert restored == path


# ── Inventory ───────────────────────────────────────────────────────────────


def test_inventory_valid_and_sorted() -> None:
    rel1 = KnowledgeRelation(
        id="rel:2",
        source_id="k:a",
        target_id="k:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:1",
        source_id="k:b",
        target_id="k:c",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    c1 = Contradiction(id="contra:2", item_a_id="k:a", item_b_id="k:b")
    c2 = Contradiction(id="contra:1", item_a_id="k:c", item_b_id="k:d")
    binding = _sample_binding()

    inv = DomainMemoryKnowledgeInventory(
        relations=(rel1, rel2),
        contradictions=(c1, c2),
        proposal_bindings=(binding,),
    )
    # deterministically sorted by id
    assert [r.id for r in inv.relations] == ["rel:1", "rel:2"]
    assert [c.id for c in inv.contradictions] == ["contra:1", "contra:2"]
    assert inv.proposal_bindings == (binding,)


def test_inventory_rejects_non_canonical_types() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeInventory(relations=("not-a-relation",))  # type: ignore[arg-type]
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeInventory(contradictions=("not-a-contradiction",))  # type: ignore[arg-type]
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeInventory(proposal_bindings=("not-a-binding",))  # type: ignore[arg-type]


def test_inventory_rejects_duplicate_ids() -> None:
    rel1 = KnowledgeRelation(
        id="rel:1",
        source_id="k:a",
        target_id="k:b",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    rel2 = KnowledgeRelation(
        id="rel:1",
        source_id="k:c",
        target_id="k:d",
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.9),
    )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeInventory(relations=(rel1, rel2))


# ── ProjectionRequest ───────────────────────────────────────────────────────


def test_request_valid_and_canonical_sorting() -> None:
    req = DomainMemoryKnowledgeProjectionRequest(
        request_id="req:1",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"), DomainId("oppositions")),
        memory_view_id="view:1",
        memory_view_digest="f" * 64,
        resolution_reference_id="res:1",
        composition_reference_id="comp:1",
        permission_decision_ids=("perm:b", "perm:a"),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
    )
    assert req.request_id == "req:1"
    assert req.primary_domain == DomainId("health")
    assert req.supporting_domains == (DomainId("oppositions"), DomainId("university"))
    assert req.permission_decision_ids == ("perm:a", "perm:b")
    assert req.requested_capabilities == (
        DomainMemoryKnowledgeProjectionCapability.RELATIONS,
        DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
    )


def test_request_rejects_invalid_view_digest() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeProjectionRequest(
            request_id="req:1",
            primary_domain=DomainId("health"),
            supporting_domains=(),
            memory_view_id="view:1",
            memory_view_digest="not-a-64-hex-digest",
            resolution_reference_id="res:1",
            composition_reference_id="comp:1",
            permission_decision_ids=(),
            requested_capabilities=(),
        )


def test_request_rejects_blank_fields() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeProjectionRequest(
            request_id="   ",
            primary_domain=DomainId("health"),
            supporting_domains=(),
            memory_view_id="view:1",
            memory_view_digest="f" * 64,
            resolution_reference_id="res:1",
            composition_reference_id="comp:1",
            permission_decision_ids=(),
            requested_capabilities=(),
        )


def test_request_serialization_rejects_unknown_fields() -> None:
    req = DomainMemoryKnowledgeProjectionRequest(
        request_id="req:1",
        primary_domain=DomainId("health"),
        supporting_domains=(DomainId("university"),),
        memory_view_id="view:1",
        memory_view_digest="a" * 64,
        resolution_reference_id="res:1",
        composition_reference_id="comp:1",
        permission_decision_ids=("perm:1",),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
    )
    data = req.to_dict()
    restored = DomainMemoryKnowledgeProjectionRequest.from_dict(data)
    assert restored == req

    data["unknown_key"] = "bad"
    with pytest.raises(DomainMemoryKnowledgeSerializationError):
        DomainMemoryKnowledgeProjectionRequest.from_dict(data)


def _base_request(**overrides):  # type: ignore[no-untyped-def]
    params = {
        "request_id": "req:1",
        "primary_domain": DomainId("health"),
        "supporting_domains": (DomainId("university"),),
        "memory_view_id": "view:1",
        "memory_view_digest": "a" * 64,
        "resolution_reference_id": "res:1",
        "composition_reference_id": "comp:1",
        "permission_decision_ids": ("perm:1",),
        "requested_capabilities": (),
        "trace_id": None,
        "session_id": None,
        "temporal_reference": None,
    }
    params.update(overrides)
    return DomainMemoryKnowledgeProjectionRequest(**params)


def _request_with(**overrides):  # type: ignore[no-untyped-def]
    return _base_request(**overrides)


@pytest.mark.parametrize(
    "field",
    [
        "supporting_domains",
        "permission_decision_ids",
        "resolution_reference_id",
        "composition_reference_id",
        "temporal_reference",
        "requested_capabilities",
        "trace_id",
        "session_id",
    ],
)
def test_request_digest_binds_authority_field(field: str) -> None:
    if field == "supporting_domains":
        alt = _request_with(supporting_domains=(DomainId("oppositions"),))
    elif field == "permission_decision_ids":
        alt = _request_with(permission_decision_ids=("perm:2",))
    elif field == "resolution_reference_id":
        alt = _request_with(resolution_reference_id="res:2")
    elif field == "composition_reference_id":
        alt = _request_with(composition_reference_id="comp:2")
    elif field == "temporal_reference":
        alt = _request_with(
            temporal_reference="2026-09-07T12:00:00+00:00",
        )
    elif field == "requested_capabilities":
        alt = _request_with(
            requested_capabilities=(
                DomainMemoryKnowledgeProjectionCapability.RELATIONS,
            ),
        )
    elif field == "trace_id":
        alt = _request_with(trace_id="trace:2")
    else:
        alt = _request_with(session_id="session:2")
    assert _base_request().digest != alt.digest
    assert len(alt.digest) == 64


def test_request_digest_covers_all_authority_fields() -> None:
    req = _base_request(
        supporting_domains=(DomainId("university"), DomainId("oppositions")),
        permission_decision_ids=("perm:1", "perm:2"),
        resolution_reference_id="res:9",
        composition_reference_id="comp:9",
        trace_id="trace:9",
        session_id="session:9",
        temporal_reference="2026-09-07T12:00:00+00:00",
        requested_capabilities=(DomainMemoryKnowledgeProjectionCapability.RELATIONS,),
    )
    payload = req.to_dict()
    for field in (
        "request_id",
        "primary_domain",
        "supporting_domains",
        "memory_view_id",
        "memory_view_digest",
        "resolution_reference_id",
        "composition_reference_id",
        "permission_decision_ids",
        "requested_capabilities",
        "trace_id",
        "session_id",
        "temporal_reference",
    ):
        assert field in payload


# ── Projection Result ───────────────────────────────────────────────────────


def test_projection_valid_and_content_bound_id() -> None:
    rel = DomainMemoryKnowledgeRelationRef(
        relation_id="rel:1",
        source_reference_id="ref:1",
        target_reference_id="ref:2",
        kind="supports",
    )
    proj = DomainMemoryKnowledgeProjection.create(
        request_id="req:1",
        request_digest="c" * 64,
        memory_view_id="view:1",
        memory_view_digest="b" * 64,
        selected_reference_ids=("ref:2", "ref:1"),
        shared_identity_reference_ids=("ref:1",),
        relation_refs=(rel,),
        timeline_reference_ids=("ref:1", "ref:2"),
        unknown_ordering_reference_ids=(),
        contradiction_refs=(),
        dependency_paths=(),
        impact_paths=(),
        proposal_binding_ids=(),
        excluded_reference_ids=("ref:3",),
    )
    assert proj.selected_reference_ids == ("ref:1", "ref:2")
    assert proj.shared_identity_reference_ids == ("ref:1",)
    assert proj.excluded_reference_ids == ("ref:3",)
    assert proj.request_digest == "c" * 64
    assert len(proj.content_digest) == 64
    assert (
        proj.projection_id
        == f"domain-memory-knowledge-projection:{proj.content_digest[:16]}"
    )


def test_projection_binds_request_digest_in_identity() -> None:
    rel = DomainMemoryKnowledgeRelationRef(
        relation_id="rel:1",
        source_reference_id="ref:1",
        target_reference_id="ref:2",
        kind="supports",
    )
    first = DomainMemoryKnowledgeProjection.create(
        request_id="req:1",
        request_digest="c" * 64,
        memory_view_id="view:1",
        memory_view_digest="b" * 64,
        selected_reference_ids=("ref:1",),
        shared_identity_reference_ids=(),
        relation_refs=(rel,),
    )
    second = DomainMemoryKnowledgeProjection.create(
        request_id="req:1",
        request_digest="d" * 64,
        memory_view_id="view:1",
        memory_view_digest="b" * 64,
        selected_reference_ids=("ref:1",),
        shared_identity_reference_ids=(),
        relation_refs=(rel,),
    )
    assert first.content_digest != second.content_digest
    assert first.projection_id != second.projection_id
    assert first.to_dict()["request_digest"] == "c" * 64
    restored = DomainMemoryKnowledgeProjection.from_dict(first.to_dict())
    assert restored == first


def test_projection_rejects_overlap_between_selected_and_excluded() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeProjection.create(
            request_id="req:1",
            request_digest="c" * 64,
            memory_view_id="view:1",
            memory_view_digest="b" * 64,
            selected_reference_ids=("ref:1", "ref:2"),
            shared_identity_reference_ids=(),
            relation_refs=(),
            excluded_reference_ids=("ref:2", "ref:3"),
        )


def test_projection_rejects_shared_identity_not_in_selected() -> None:
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeProjection.create(
            request_id="req:1",
            request_digest="c" * 64,
            memory_view_id="view:1",
            memory_view_digest="b" * 64,
            selected_reference_ids=("ref:1",),
            shared_identity_reference_ids=("ref:99",),
            relation_refs=(),
        )


def test_projection_rejects_tampered_id_or_digest() -> None:
    proj = DomainMemoryKnowledgeProjection.create(
        request_id="req:1",
        request_digest="c" * 64,
        memory_view_id="view:1",
        memory_view_digest="b" * 64,
        selected_reference_ids=("ref:1",),
        shared_identity_reference_ids=(),
        relation_refs=(),
    )
    with pytest.raises(DomainMemoryKnowledgeContractError):
        DomainMemoryKnowledgeProjection(
            projection_id="domain-memory-knowledge-projection:tampered1234567",
            request_id=proj.request_id,
            request_digest=proj.request_digest,
            memory_view_id=proj.memory_view_id,
            memory_view_digest=proj.memory_view_digest,
            selected_reference_ids=proj.selected_reference_ids,
            shared_identity_reference_ids=proj.shared_identity_reference_ids,
            relation_refs=proj.relation_refs,
            timeline_reference_ids=proj.timeline_reference_ids,
            unknown_ordering_reference_ids=proj.unknown_ordering_reference_ids,
            contradiction_refs=proj.contradiction_refs,
            dependency_paths=proj.dependency_paths,
            impact_paths=proj.impact_paths,
            proposal_binding_ids=proj.proposal_binding_ids,
            excluded_reference_ids=proj.excluded_reference_ids,
            content_digest=proj.content_digest,
        )


def test_projection_serialization_round_trip() -> None:
    proj = DomainMemoryKnowledgeProjection.create(
        request_id="req:1",
        request_digest="c" * 64,
        memory_view_id="view:1",
        memory_view_digest="b" * 64,
        selected_reference_ids=("ref:1",),
        shared_identity_reference_ids=(),
        relation_refs=(),
    )
    data = proj.to_dict()
    restored = DomainMemoryKnowledgeProjection.from_dict(data)
    assert restored == proj

    data["raw_content"] = "leak"
    with pytest.raises(DomainMemoryKnowledgeSerializationError):
        DomainMemoryKnowledgeProjection.from_dict(data)


# ── Protocol check ──────────────────────────────────────────────────────────


def test_projection_protocol_is_runtime_checkable() -> None:
    assert (
        getattr(DomainMemoryKnowledgeIntegrator, "_is_runtime_protocol", False) is True
    )
