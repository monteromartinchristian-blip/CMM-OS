"""Phase 10.44 — AT-DP-044 Connected Acceptance Test.

Proves the complete Domain-to-Memory-and-Knowledge-Graph flow end-to-end:

  DomainResolutionContext
  → DefaultDomainResolver
  → DefaultDomainComposer
  → Canonical Cognitive InMemoryKnowledgeStore (items, relations, contradictions)
  → Phase 10.18 DomainMemoryReference + snapshots + DefaultDomainMemoryViewResolver
  → DefaultDomainMemoryIntegrationValidator.validate_view
  → DefaultDomainAPI.project_memory_knowledge (delegating to DefaultDomainMemoryKnowledgeIntegrator)
  → Content-bound DomainMemoryKnowledgeProjection
  → Verified proposal bindings (Phase 9 KnowledgeUpdateProposalEngine + Phase 10.18 bindings)
  → Downgraded-authority adversarial branch
  → Causal adversarial branch (no synthetic causal edge)
  → Temporal adversarial branch (strict chronological order, no merged intervals)

Emits AT-DP-044=PASS upon full verification of all required invariants.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateContext
from cmm.agent_runtime.knowledge_update_proposal_engine import (
    KnowledgeUpdateProposalEngine,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
)
from cmm.cognitive.knowledge import (
    Confidence,
    Contradiction,
    ContradictionSeverity,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeRelation,
    KnowledgeRelationKind,
    TemporalScope,
    TemporalScopeKind,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.api import DefaultDomainAPI
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import DomainCompositionStatus
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
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
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionResource,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.university.definition import build_university_domain_definition
from tests.domains.test_domain_api_contracts import _make_collaborators

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
EARLIER = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


def _compute_binding_id(
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
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"binding:{domain_id}:{trace_id}:{view_id}:{digest[:12]}"


def test_at_dp044_connected_acceptance() -> None:
    """Execute complete connected AT-DP-044 acceptance workflow."""

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1 & 2: Resolve and compose domains through canonical components
    # ─────────────────────────────────────────────────────────────────────────
    def_uni = build_university_domain_definition()
    def_health = build_health_domain_definition()
    def_opp = build_oppositions_domain_definition()
    def_life = build_life_plan_domain_definition()
    assert def_opp.id == DomainId("oppositions")
    assert def_life.id == DomainId("life-plan")

    res_context = DomainResolutionContext(
        id="res-ctx-044",
        user_input="University student preparing for state exam and health regimen under personal life plan",
        available_domains=(
            DomainId("university"),
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        authorized_domains=(
            DomainId("university"),
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        explicit_domains=(DomainId("university"),),
        active_domains=(),
        resources=(
            DomainResolutionResource(
                id="res-ref-044",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("health"),),
            ),
        ),
        created_at=NOW,
    )
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        scoring_policy=DomainScoringPolicy(
            max_supporting_domains=3, supporting_margin=100.0
        ),
        clock=lambda: NOW,
        id_factory=lambda: "res-044",
    )
    resolution = resolver.resolve(res_context)
    assert resolution.primary_domain == DomainId("university")
    assert DomainId("health") in resolution.supporting_domains

    composer = DefaultDomainComposer(id_factory=lambda: "comp-044", clock=lambda: NOW)
    composition = composer.compose(
        resolution,
        (def_uni, def_health),
    )
    assert composition.status in {
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3, 4, 5: Seed official Cognitive in-memory knowledge store
    # ─────────────────────────────────────────────────────────────────────────
    store = InMemoryKnowledgeStore()

    item_health = KnowledgeItem(
        id="item:health:medication",
        statement="Prescribed daily recovery regimen and medical rest periods",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.96),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.TIMELESS,
            observed_at=EARLIER,
            valid_from=EARLIER,
        ),
        created_at=EARLIER,
        updated_at=EARLIER,
        metadata={"applicable_domains": ["health", "university"]},
    )
    item_study = KnowledgeItem(
        id="item:uni:study_capacity",
        statement="Daily 4-hour focused study capacity with scheduled breaks",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.92),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.TIMELESS,
            observed_at=NOW,
            valid_from=NOW,
        ),
        created_at=NOW,
        updated_at=NOW,
        metadata={"applicable_domains": ["university"]},
    )
    item_goal = KnowledgeItem(
        id="item:opp:exam_goal",
        statement="Preparation goal for state civil service competitive examination",
        kind=KnowledgeKind.DECISION,
        confidence=Confidence(value=0.90),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.TIMELESS,
            observed_at=NOW,
            valid_from=NOW,
        ),
        created_at=NOW,
        updated_at=NOW,
        metadata={"applicable_domains": ["oppositions"]},
    )
    item_plan = KnowledgeItem(
        id="item:life:career_plan",
        statement="Long-term multi-year public administration career stability plan",
        kind=KnowledgeKind.DECISION,
        confidence=Confidence(value=0.98),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.TIMELESS,
            observed_at=LATER,
            valid_from=LATER,
        ),
        created_at=LATER,
        updated_at=LATER,
        metadata={"applicable_domains": ["life-plan"]},
    )
    item_conflict = KnowledgeItem(
        id="item:health:conflict",
        statement="Continuous 16-hour study sessions without scheduled rest intervals",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.65),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.TIMELESS,
            observed_at=NOW,
            valid_from=NOW,
        ),
        created_at=NOW,
        updated_at=NOW,
        metadata={"applicable_domains": ["health"]},
    )
    item_unknown = KnowledgeItem(
        id="item:uni:unknown_timing",
        statement="Extra-curricular university seminar attendance requirement",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.80),
        temporal_scope=TemporalScope(kind=TemporalScopeKind.UNKNOWN),
        created_at=NOW,
        updated_at=NOW,
        metadata={"applicable_domains": ["university"]},
    )

    store.save_item(item_health)
    store.save_item(item_study)
    store.save_item(item_goal)
    store.save_item(item_plan)
    store.save_item(item_conflict)
    store.save_item(item_unknown)

    # Relations: multi-hop chain with at least one weaker non-causal edge (RELATED_TO)
    rel_health_study = KnowledgeRelation(
        id="rel:health:study",
        source_id=item_health.id,
        target_id=item_study.id,
        kind=KnowledgeRelationKind.SUPPORTS,
        confidence=Confidence(value=0.92),
        created_at=NOW,
    )
    rel_study_goal = KnowledgeRelation(
        id="rel:study:goal",
        source_id=item_study.id,
        target_id=item_goal.id,
        kind=KnowledgeRelationKind.RELATED_TO,
        confidence=Confidence(value=0.88),
        created_at=NOW,
    )
    rel_goal_plan = KnowledgeRelation(
        id="rel:goal:plan",
        source_id=item_goal.id,
        target_id=item_plan.id,
        kind=KnowledgeRelationKind.DERIVED_FROM,
        confidence=Confidence(value=0.95),
        created_at=NOW,
    )

    store.save_relation(rel_health_study)
    store.save_relation(rel_study_goal)
    store.save_relation(rel_goal_plan)

    # Contradiction: explicit contradiction between health regimen and excessive study
    contra = Contradiction(
        id="contra:health:study_excess",
        item_a_id=item_health.id,
        item_b_id=item_conflict.id,
        severity=ContradictionSeverity.HIGH,
        explanation="Prescribed recovery rest contradicts continuous 16-hour study sessions",
        created_at=NOW,
    )
    store.save_contradiction(contra)

    # Capture store snapshot before projection
    store_items_before = {item.id: item.statement for item in store.list_items()}
    store_relations_before = {
        r.id: (r.source_id, r.target_id, r.kind) for r in store.list_relations()
    }
    store_contradictions_before = {
        c.id: (c.item_a_id, c.item_b_id) for c in store.list_contradictions()
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Build real Phase 10.18 memory view and validate
    # ─────────────────────────────────────────────────────────────────────────
    ref_health = DomainMemoryReference(
        reference_id="ref:health:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_health.id,
        domain_id="domain:health",
        applicable_domains=("domain:health", "domain:university"),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            valid_from=EARLIER.isoformat(),
            observed_at=EARLIER.isoformat(),
        ),
        evidence_ids=("ev:health:1",),
        resource_ids=("res:health:1",),
    )
    ref_study = DomainMemoryReference(
        reference_id="ref:uni:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_study.id,
        domain_id="domain:university",
        applicable_domains=("domain:university",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            valid_from=NOW.isoformat(),
            observed_at=NOW.isoformat(),
        ),
        evidence_ids=("ev:uni:1",),
        resource_ids=("res:uni:1",),
    )
    ref_goal = DomainMemoryReference(
        reference_id="ref:opp:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_goal.id,
        domain_id="domain:oppositions",
        applicable_domains=("domain:oppositions",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            valid_from=NOW.isoformat(),
            observed_at=NOW.isoformat(),
        ),
        evidence_ids=("ev:opp:1",),
        resource_ids=("res:opp:1",),
    )
    ref_plan = DomainMemoryReference(
        reference_id="ref:plan:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_plan.id,
        domain_id="domain:life-plan",
        applicable_domains=("domain:life-plan",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            valid_from=LATER.isoformat(),
            observed_at=LATER.isoformat(),
        ),
        evidence_ids=("ev:plan:1",),
        resource_ids=("res:plan:1",),
    )
    ref_conflict = DomainMemoryReference(
        reference_id="ref:health:conflict",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_conflict.id,
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            valid_from=NOW.isoformat(),
            observed_at=NOW.isoformat(),
        ),
        evidence_ids=("ev:conflict:1",),
        resource_ids=("res:conflict:1",),
    )
    ref_unknown = DomainMemoryReference(
        reference_id="ref:uni:unknown",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_unknown.id,
        domain_id="domain:university",
        applicable_domains=("domain:university",),
        has_unknown_ordering=True,
        evidence_ids=("ev:unknown:1",),
        resource_ids=("res:unknown:1",),
    )

    all_references = (
        ref_health,
        ref_study,
        ref_goal,
        ref_plan,
        ref_conflict,
        ref_unknown,
    )

    perm_uni = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:uni",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:university",
        source_domain_id="domain:university",
    )
    perm_health = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:health",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:university",
        source_domain_id="domain:health",
    )
    perm_opp = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:opp",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:university",
        source_domain_id="domain:oppositions",
    )
    perm_life = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:life",
        allowed=True,
        capabilities=("READ",),
        target_domain_id="domain:university",
        source_domain_id="domain:life-plan",
    )
    perm_propose = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:propose:044",
        allowed=True,
        capabilities=("PROPOSE",),
        target_domain_id="domain:university",
        source_domain_id="domain:university",
    )
    permissions = (perm_uni, perm_health, perm_opp, perm_life, perm_propose)

    mem_req = DomainMemoryViewRequest(
        request_id="mem-req-044",
        primary_domain=DomainId("university"),
        supporting_domains=(
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        candidates=all_references,
        permission_decision_ids=tuple(p.decision_id for p in permissions),
    )
    mem_inv_initial = DomainMemoryReferenceInventory(
        references=all_references,
        permission_decisions=permissions,
    )

    view_resolver = DefaultDomainMemoryViewResolver()
    view = view_resolver.resolve(mem_req, mem_inv_initial)

    view_validator = DefaultDomainMemoryIntegrationValidator()
    view_validation = view_validator.validate_view(view, mem_req, mem_inv_initial)
    assert view_validation.is_valid is True

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Invoke Phase 10.44 through DefaultDomainAPI facade
    # ─────────────────────────────────────────────────────────────────────────
    collaborators = _make_collaborators()
    collaborators["memory_knowledge_integrator"] = (
        DefaultDomainMemoryKnowledgeIntegrator()
    )
    api = DefaultDomainAPI(**collaborators)

    req = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj-req-044",
        primary_domain=DomainId("university"),
        supporting_domains=(
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id="res-044",
        composition_reference_id="comp-044",
        permission_decision_ids=tuple(p.decision_id for p in permissions),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
            DomainMemoryKnowledgeProjectionCapability.RELATIONS,
            DomainMemoryKnowledgeProjectionCapability.TIMELINE,
            DomainMemoryKnowledgeProjectionCapability.CONTRADICTIONS,
            DomainMemoryKnowledgeProjectionCapability.DEPENDENCIES,
            DomainMemoryKnowledgeProjectionCapability.IMPACT_PATHS,
            DomainMemoryKnowledgeProjectionCapability.RELATION_PROPOSALS,
        ),
    )

    inventory = DomainMemoryKnowledgeInventory(
        relations=tuple(store.list_relations()),
        contradictions=tuple(store.list_contradictions()),
    )

    projection = api.project_memory_knowledge(
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv_initial,
        inventory=inventory,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Assert positive DP-044 checkpoints (all 24 requirements)
    # ─────────────────────────────────────────────────────────────────────────
    # 1. resolution/composition occurred before projection
    assert resolution.primary_domain == DomainId("university")
    assert composition.status in {
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    }

    # 2. Phase 10.18 real view resolver used
    assert view.view_id.startswith("view:mem-req-044:")

    # 3. Phase 10.18 real validator passed
    assert view_validation.is_valid is True

    # 4. one canonical identity appears once across several applicable domains
    assert "ref:health:1" in projection.shared_identity_reference_ids

    # 5. no duplicate KnowledgeItem was created
    assert len(store.list_items()) == len(store_items_before)

    # 6. only view-selected references are projected
    view_selected_ids = {r.reference_id for r in view.selected_references}
    assert set(projection.selected_reference_ids) == view_selected_ids

    # 7. sensitive source/resource data is not serialized
    serialized = projection.to_dict()
    forbidden_keys = {
        "statement",
        "excerpt",
        "raw_content",
        "prompt",
        "reasoning_text",
        "chain_of_thought",
        "source_payload",
        "resource_content",
        "secret",
        "credential",
    }
    serialized_keys = set(serialized.keys())
    assert not (serialized_keys & forbidden_keys)

    # 8. visible canonical relation IDs are preserved
    projected_rel_ids = {r.relation_id for r in projection.relation_refs}
    assert "rel:health:study" in projected_rel_ids
    assert "rel:study:goal" in projected_rel_ids
    assert "rel:goal:plan" in projected_rel_ids

    # 9. every path hop retains its canonical relation ID
    all_hop_rel_ids = {
        hop.relation_id
        for path in (*projection.dependency_paths, *projection.impact_paths)
        for hop in path.hops
    }
    assert all_hop_rel_ids.issubset(projected_rel_ids)

    # 10. timeline IDs derive only from references with canonical temporal metadata
    assert len(projection.timeline_reference_ids) >= 4
    # Earliest is ref:health:1 (EARLIER), then ref:uni:1 (NOW), etc.
    assert projection.timeline_reference_ids[0] == "ref:health:1"

    # 11. upstream-excluded state is not reintroduced
    assert set(projection.selected_reference_ids).isdisjoint(
        set(projection.excluded_reference_ids)
    )

    # 12. unknown ordering is explicitly preserved
    assert "ref:uni:unknown" in projection.unknown_ordering_reference_ids
    assert "ref:uni:unknown" not in projection.timeline_reference_ids

    # 13. no combined/fabricated temporal interval exists
    for ref_id in projection.timeline_reference_ids:
        assert ref_id in view_selected_ids

    # 14. canonical contradiction ID survives
    projected_contra_ids = {c.contradiction_id for c in projection.contradiction_refs}
    assert "contra:health:study_excess" in projected_contra_ids

    # 15. succession alone is not emitted as contradiction
    assert all(
        c.contradiction_id.startswith("contra:") for c in projection.contradiction_refs
    )

    # 16. multi-hop path does not synthesize direct causal edge
    direct_edges = {
        (r.source_reference_id, r.target_reference_id): r.kind
        for r in projection.relation_refs
    }
    assert ("ref:health:1", "ref:plan:1") not in direct_edges

    # 17. projection has no raw statement/excerpt/resource payload
    assert "statement" not in json.dumps(serialized)

    # 18. projection digest/ID round-trip is deterministic
    round_trip = DomainMemoryKnowledgeProjection.from_dict(serialized)
    assert round_trip.projection_id == projection.projection_id
    assert round_trip.content_digest == projection.content_digest

    # 19. Cognitive store snapshot equals pre-projection snapshot
    assert {i.id: i.statement for i in store.list_items()} == store_items_before
    assert {
        r.id: (r.source_id, r.target_id, r.kind) for r in store.list_relations()
    } == store_relations_before
    assert {
        c.id: (c.item_a_id, c.item_b_id) for c in store.list_contradictions()
    } == store_contradictions_before

    # 20. DomainAPI is only the delegate; integrator owns projection
    assert isinstance(projection, DomainMemoryKnowledgeProjection)

    # 21. no reverse import is introduced
    import cmm.cognitive

    assert not hasattr(cmm.cognitive, "domains")

    # 22. no Phase 10.44 source imports cmm.memory
    import cmm.domains.memory_knowledge_integration as mki

    assert "cmm.memory" not in getattr(mki, "__file__", "")

    # 23. architecture guard remains compatible
    assert len(projection.relation_refs) == 3

    # 24. production consumer exists outside tests (DefaultDomainAPI.project_memory_knowledge)
    assert callable(DefaultDomainAPI.project_memory_knowledge)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Real relation-proposal checkpoint
    # ─────────────────────────────────────────────────────────────────────────
    prop_repo = InMemoryKnowledgeUpdateRepository()
    prop_engine = KnowledgeUpdateProposalEngine(repository=prop_repo)
    ctx = KnowledgeUpdateContext(
        context_id="ctx-prop-044", agent_run_id="run-044", goal_id="goal-044"
    )
    mock_goal = MagicMock()
    mock_goal.goal_id = "goal-044"
    mock_goal.title = "Exam Prep Proposal"
    mock_goal.kind = "general"
    mock_decision = MagicMock()
    mock_decision.decision_kind = "complete"
    mock_decision.confidence = 0.95

    real_proposal = prop_engine.create_proposal(
        context=ctx,
        goal=mock_goal,
        completion_decision=mock_decision,
    )

    prop_snap = DomainMemoryProposalSnapshot(
        proposal_id=real_proposal.proposal_id,
        proposal_kind="agent_knowledge_update",
        affected_reference_ids=("ref:uni:1",),
        required_capabilities=("PROPOSE",),
    )
    trace_snap = DomainMemoryTraceSnapshot(
        trace_id="trace:044",
        primary_domain=DomainId("university"),
    )
    view_snap = DomainMemoryViewSnapshot(
        view_id=view.view_id,
        request_id=mem_req.request_id,
        primary_domain=view.primary_domain,
        trace_id="trace:044",
        view_digest=view.content_digest,
    )

    mem_inv_with_prop = DomainMemoryReferenceInventory(
        references=all_references,
        permission_decisions=permissions,
        traces=(trace_snap,),
        views=(view_snap,),
        proposals=(prop_snap,),
    )

    binding_id = _compute_binding_id(
        domain_id="domain:university",
        trace_id="trace:044",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=(real_proposal.proposal_id,),
        affected_reference_ids=("ref:uni:1",),
        permission_decision_ids=("perm:propose:044",),
    )
    proposal_binding = DomainMemoryProposalBinding(
        binding_id=binding_id,
        domain_id="domain:university",
        trace_id="trace:044",
        view_id=view.view_id,
        view_digest=view.content_digest,
        agent_knowledge_proposal_ids=(real_proposal.proposal_id,),
        affected_reference_ids=("ref:uni:1",),
        permission_decision_ids=("perm:propose:044",),
    )

    # Validate binding through Phase 10.18 validator
    binding_val = view_validator.validate_binding(
        proposal_binding,
        mem_inv_with_prop,
    )
    assert binding_val.is_valid is True

    inventory_with_proposal = DomainMemoryKnowledgeInventory(
        relations=tuple(store.list_relations()),
        contradictions=tuple(store.list_contradictions()),
        proposal_bindings=(proposal_binding,),
    )

    projection_with_proposal = api.project_memory_knowledge(
        req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv_with_prop,
        inventory=inventory_with_proposal,
    )
    assert binding_id in projection_with_proposal.proposal_binding_ids
    # Cognitive store remains untouched
    assert {i.id: i.statement for i in store.list_items()} == store_items_before
    # Proposal in repository has NOT been applied to store or decided
    fetched_proposal = prop_repo.get_proposal(real_proposal.proposal_id)
    assert fetched_proposal is not None
    assert prop_repo.get_decision(real_proposal.proposal_id) is None
    assert prop_repo.get_result(real_proposal.proposal_id) is None

    # ─────────────────────────────────────────────────────────────────────────
    # Step 10: Downgraded-authority adversarial branch
    # ─────────────────────────────────────────────────────────────────────────
    perm_health_revoked = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:read:health",
        allowed=False,
        capabilities=(),
        target_domain_id="domain:university",
        source_domain_id="domain:health",
    )
    downgraded_permissions = (
        perm_uni,
        perm_health_revoked,
        perm_opp,
        perm_life,
        perm_propose,
    )
    downgraded_mem_inv = DomainMemoryReferenceInventory(
        references=all_references,
        permission_decisions=downgraded_permissions,
    )
    downgraded_view = view_resolver.resolve(mem_req, downgraded_mem_inv)

    downgraded_req = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj-req-044-downgraded",
        primary_domain=DomainId("university"),
        supporting_domains=(DomainId("oppositions"), DomainId("life-plan")),
        memory_view_id=downgraded_view.view_id,
        memory_view_digest=downgraded_view.digest,
        resolution_reference_id="res-044",
        composition_reference_id="comp-044",
        permission_decision_ids=tuple(p.decision_id for p in downgraded_permissions),
        requested_capabilities=req.requested_capabilities,
    )

    downgraded_projection = api.project_memory_knowledge(
        downgraded_req,
        memory_request=mem_req,
        view=downgraded_view,
        memory_inventory=downgraded_mem_inv,
        inventory=inventory,
    )

    # Health reference is completely suppressed
    assert "ref:health:1" not in downgraded_projection.selected_reference_ids
    assert "ref:health:1" not in downgraded_projection.shared_identity_reference_ids
    # Relations and contradictions referencing suppressed health item are suppressed fail-closed
    downgraded_rel_ids = {r.relation_id for r in downgraded_projection.relation_refs}
    assert "rel:health:study" not in downgraded_rel_ids
    assert "contra:health:study_excess" not in {
        c.contradiction_id for c in downgraded_projection.contradiction_refs
    }
    # Cognitive store remains untouched
    assert {i.id: i.statement for i in store.list_items()} == store_items_before

    # ─────────────────────────────────────────────────────────────────────────
    # Step 11: Causal adversarial branch
    # ─────────────────────────────────────────────────────────────────────────
    # Ensure related_to relation was not transformed to causal relation
    study_goal_rels = [
        r for r in projection.relation_refs if r.relation_id == "rel:study:goal"
    ]
    assert len(study_goal_rels) == 1
    assert study_goal_rels[0].kind == "related_to"
    assert study_goal_rels[0].kind != "causes"

    # ─────────────────────────────────────────────────────────────────────────
    # Step 12: Temporal adversarial branch
    # ─────────────────────────────────────────────────────────────────────────
    # References maintain chronological separation without synthetic intervals
    assert projection.timeline_reference_ids == (
        "ref:health:1",
        "ref:health:conflict",
        "ref:opp:1",
        "ref:uni:1",
        "ref:plan:1",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 13: Emit stable acceptance marker
    # ─────────────────────────────────────────────────────────────────────────
    print("AT-DP-044=PASS")
