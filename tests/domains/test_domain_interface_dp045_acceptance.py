"""Phase 10.45 — AT-DP-045 Connected Acceptance Test.

Proves the complete Domain-to-Interface integration flow end-to-end over
canonical implementations and official in-memory stores only:

  real Domain registry (official DomainRegistry + real definitions)
  → DefaultDomainResolver (real DomainResolutionResult)
  → DefaultDomainComposer (real composition)
  → canonical session/context + canonical presentation state
  → canonical operation/workflow refs + Phase 9 approval repository
  → Phase 10.15 permission registry/evaluator
  → canonical observability state
  → Phase 10.44 memory/knowledge projection (real view resolver + integrator)
  → DefaultDomainAPI.project_interface / submit_interface_intent
  → DefaultDomainInterfaceIntegrator
  → five interface-facing views bound to the same canonical authority

Then exercises all twelve mandatory adversarial branches:

  1. resolution/composition mismatch → fail closed
  2. denied supporting-domain access → never authorized/disclosed
  3. disabled/degraded status → preserved, never upgraded
  4. selector privilege escalation → rejected
  5. pending approval → remains pending
  6. memory proposal → remains proposal; stores unchanged
  7. unresolved contradiction → remains unresolved
  8. confidence → never strengthened
  9. superseded/invalidated/expired knowledge → cannot re-enter
  10. correlation/dependency → never strengthened to causation
  11. partial composition → remains partial
  12. absent update authority → update not fabricated

Emits AT-DP-045=PASS upon full verification of all required invariants.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    SensitivityLevel,
)
from cmm.agent_runtime.enums import ApprovalRequestStatus
from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateContext
from cmm.agent_runtime.knowledge_update_proposal_engine import (
    KnowledgeUpdateProposalEngine,
)
from cmm.agent_runtime.knowledge_update_repository import (
    InMemoryKnowledgeUpdateRepository,
)
from cmm.cognitive.knowledge import (
    Confidence,
    KnowledgeItem,
    KnowledgeKind,
    TemporalScope,
    TemporalScopeKind,
)
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.api import DefaultDomainAPI
from cmm.domains.composer import DefaultDomainComposer
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
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    CrossDomainInterfaceView,
    DomainCenterView,
    DomainInterfaceIntent,
    DomainInterfaceIntentKind,
    DomainInterfaceIntentResult,
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
    DomainInterfaceStatus,
    DomainReviewCenterView,
    DomainSelectorView,
)
from cmm.domains.life_plan.definition import build_life_plan_domain_definition
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
    DomainMemoryKnowledgeProjection,
    DomainMemoryKnowledgeProjectionCapability,
    DomainMemoryKnowledgeProjectionRequest,
)
from cmm.domains.memory_validation import DefaultDomainMemoryIntegrationValidator
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver
from cmm.domains.observability_contracts import (
    DomainMetricMeasurement,
    DomainMetricStatus,
    DomainObservabilityLogEntry,
)
from cmm.domains.oppositions.definition import build_oppositions_domain_definition
from cmm.domains.permission_contracts import (
    CrossDomainPermissionDecision,
    CrossDomainPermissionRequest,
    DomainPermissionPolicy,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.presentation_contracts import (
    DomainPresentationItemType,
    DomainPresentationPlan,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionResource,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.session_contracts import DomainSessionContext
from cmm.domains.university.definition import build_university_domain_definition
from tests.domains.test_domain_api_contracts import _make_collaborators
from tests.domains.test_domain_interface_integration import (
    _make_approval,
    _make_contradiction,
    _make_cross_domain_result,
    _make_cross_domain_snapshot,
    _make_dependency,
    _make_domain_definition,
    _make_item,
    _make_observability_report,
    _make_operation_approval,
    _make_par,
    _make_presentation_with_items,
    _make_transfer,
    _mark_degraded,
)

NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
CUR_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
CUR_TO = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
OLD_FROM = datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)
OLD_TO = datetime(2026, 7, 31, 0, 0, tzinfo=timezone.utc)

_RESOLUTION_ID = "res-045"
_COMPOSITION_ID = "comp-045"
_SESSION_ID = "session:045"
_PRIMARY = "domain:university"
_SUPPORTING = ("domain:health", "domain:oppositions", "domain:life-plan")

# Superseded/invalidated/expired references that canonical Phase 10.18 upstream
# authority excludes; they must never re-enter through the Phase 10.45 seam.
_STALE_REFERENCE_IDS = frozenset(
    {"ref:uni:history", "ref:health:invalidated", "ref:opp:expired"}
)


def test_at_dp045_connected_acceptance() -> None:
    """Execute the complete connected AT-DP-045 acceptance workflow."""

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Resolve and compose real domains through canonical components
    # ─────────────────────────────────────────────────────────────────────────
    def_uni = build_university_domain_definition()
    def_health = build_health_domain_definition()
    def_opp = build_oppositions_domain_definition()
    def_life = build_life_plan_domain_definition()
    definitions = (def_uni, def_health, def_opp, def_life)

    res_context = DomainResolutionContext(
        id="res-ctx-045",
        user_input=(
            "University student preparing for state exam and health regimen "
            "under personal life plan"
        ),
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
                id="res-ref-045-health",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("health"),),
            ),
            DomainResolutionResource(
                id="res-ref-045-opp",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("oppositions"),),
            ),
            DomainResolutionResource(
                id="res-ref-045-life",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("life-plan"),),
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
        id_factory=lambda: _RESOLUTION_ID,
    )
    resolution = resolver.resolve(res_context)
    assert resolution.id == _RESOLUTION_ID
    assert resolution.status == DomainResolutionStatus.RESOLVED
    assert resolution.primary_domain == DomainId("university")
    assert DomainId("health") in resolution.supporting_domains
    supporting_slugs = frozenset(str(d) for d in resolution.supporting_domains)
    assert supporting_slugs <= {
        "domain:health",
        "domain:oppositions",
        "domain:life-plan",
    }

    composer = DefaultDomainComposer(
        id_factory=lambda: _COMPOSITION_ID, clock=lambda: NOW
    )
    composition = composer.compose(resolution, definitions)
    assert composition.id == _COMPOSITION_ID
    assert composition.resolution_id == resolution.id
    assert composition.status in {
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    }
    assert str(composition.primary_domain) == _PRIMARY
    membership = {str(d) for d in composition.supporting_domains}
    membership.add(_PRIMARY)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: Real Domain registry state (official registry + real definitions)
    # ─────────────────────────────────────────────────────────────────────────
    registry = DomainRegistry()
    for definition in definitions:
        registry.register(definition)
        registry.enable(definition.id.slug)
    # A disabled domain and a degraded domain are canonical registry records;
    # their lifecycle status must be preserved by the interface projection.
    registry.register(_make_domain_definition("legal"))
    registry.disable("legal")
    registry.register(_make_domain_definition("finance"))
    _mark_degraded(registry, "finance")

    def _registry_records_state() -> tuple[tuple[object, ...], ...]:
        return tuple(
            (
                record.domain_id,
                record.status.value,
                record.definition.enabled,
            )
            for record in registry.list_records()
        )

    registry_before = _registry_records_state()
    disabled_record = registry.get_record("legal")
    assert disabled_record is not None
    assert disabled_record.status.value == "disabled"
    degraded_record = registry.get_record("finance")
    assert degraded_record is not None
    assert degraded_record.status.value == "degraded"

    # ─────────────────────────────────────────────────────────────────────────
    # Step 3: Canonical session, observability and cross-domain state
    # ─────────────────────────────────────────────────────────────────────────
    session = DomainSessionContext(
        session_id=_SESSION_ID,
        primary_domain=_PRIMARY,
        supporting_domains=_SUPPORTING,
        domain_versions={"university": "1.0.0"},
        composition_id=_COMPOSITION_ID,
        effective_profile="default",
        active_workflow_refs=("workflow:045:review",),
        approval_refs=("approval-req:045:operation:1",),
        last_resolution_id=_RESOLUTION_ID,
        updated_at=NOW,
    )

    generated_at = NOW
    observability_report = _make_observability_report(
        measurements=(
            DomainMetricMeasurement(
                name="domain.operations",
                status=DomainMetricStatus.OBSERVED,
                unit="count",
                value=3.0,
                evidence_reference_ids=("domain:university", "university"),
            ),
            DomainMetricMeasurement(
                name="domain.rules",
                status=DomainMetricStatus.OBSERVED,
                unit="count",
                value=1.0,
                evidence_reference_ids=("domain:health",),
            ),
        ),
        log_entries=(
            DomainObservabilityLogEntry(
                source_kind="domain",
                source_id="domain:university",
                category="error",
                status="failed",
                occurred_at=generated_at,
                primary_domain="domain:university",
                reference_ids=("error:uni:storage:1",),
            ),
            DomainObservabilityLogEntry(
                source_kind="domain",
                source_id="domain:health",
                category="result",
                status="resolved",
                occurred_at=generated_at,
                primary_domain="domain:health",
                reference_ids=("event:health:result:1",),
            ),
        ),
    )

    # Canonical cross-domain engine outputs: dependency/transfer/contradiction
    # state plus the completed result bound to the same composition.
    contradiction_id = "contradiction:045:study"
    snapshot = _make_cross_domain_snapshot(
        composition_id=_COMPOSITION_ID,
        transfers=(
            _make_transfer(
                source="domain:health",
                target="domain:university",
                identifier="transfer:health:university:1",
                kind="finding",
            ),
            _make_transfer(
                source="domain:university",
                target="domain:health",
                identifier="transfer:university:health:private:1",
                kind="finding",
                private=True,
            ),
            _make_transfer(
                source="domain:legal",
                target="domain:university",
                identifier="transfer:legal:university:1",
                kind="finding",
            ),
        ),
        dependencies=(
            _make_dependency(
                source="domain:university",
                target="domain:health",
                kind="requires",
                blocking=False,
                satisfied=True,
            ),
            _make_dependency(
                source="domain:university",
                target="domain:oppositions",
                kind="informs",
                blocking=False,
                satisfied=True,
            ),
        ),
        contradictions=(
            # An unresolved non-review contradiction can remain open in a
            # COMPLETED result: it never blocks and requires no review gate.
            _make_contradiction(
                contradiction_id,
                domains=(_PRIMARY, "domain:health"),
                severity="medium",
                resolved=False,
                requires_review=False,
            ),
            _make_contradiction(
                "contradiction:045:resolved",
                domains=(_PRIMARY, "domain:oppositions"),
                severity="low",
                resolved=True,
                resolution="superseded by later findings",
            ),
        ),
        decisions=(),
    )
    assert isinstance(snapshot, CrossDomainContextSnapshot)
    result = _make_cross_domain_result(
        result_id="cross-domain-result:045",
        status=CrossDomainStatus.COMPLETED,
        composition_id=_COMPOSITION_ID,
        dependencies=snapshot.dependencies,
        contradictions=(
            # The consolidated result is COMPLETED: the contradiction remains
            # open but no blocking dependency, reached limit or required review
            # condition exists, and the run produced a useful recommendation.
            _make_contradiction(
                contradiction_id,
                domains=(_PRIMARY, "domain:health"),
                severity="medium",
                resolved=False,
                requires_review=False,
            ),
        ),
        decisions=(),
        recommendations=("recommendation:045:study:schedule",),
    )
    assert isinstance(result, CrossDomainResult)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 4: Phase 9 approval repository (pending + terminal approval state)
    # ─────────────────────────────────────────────────────────────────────────
    approval_repo = InMemoryApprovalRepository()
    cross_requirement = _make_par(
        action=PermissionCapability.DOMAIN_CROSS_ACCESS,
        requirement_id="permission-requirement:045:cross:1",
        actor_id="actor:045",
        session_id=_SESSION_ID,
        domain_id=_PRIMARY,
        resource_id="resource:045:health",
        target_domain="domain:health",
        reason_code="cross_access_requires_approval",
    )
    approval_repo.add_request(
        _make_approval(
            approval_id="approval-req:045:cross:1",
            permission_requirement=cross_requirement,
            operation_id="operation:045:cross",
        )
    )
    approval_repo.add_request(
        _make_operation_approval(
            "approval-req:045:operation:1",
            reason_code="domain_operation.risk_high",
            primary_domain=_PRIMARY,
            supporting_domains=_SUPPORTING,
            operation_id="operation:045:assess",
            workflow_id="workflow:045:review",
        )
    )
    # Terminal approvals never surface as review-required state.
    approval_repo.add_request(
        _make_operation_approval(
            "approval-req:045:operation:approved:1",
            status=ApprovalRequestStatus.APPROVED,
            primary_domain=_PRIMARY,
        )
    )
    approval_repo.add_request(
        _make_approval(
            approval_id="approval-req:045:legal:rejected:1",
            status=ApprovalRequestStatus.REJECTED,
            permission_requirement=_make_par(
                action=PermissionCapability.DOMAIN_CROSS_ACCESS,
                requirement_id="permission-requirement:045:legal:1",
                actor_id="actor:045",
                session_id=_SESSION_ID,
                domain_id=_PRIMARY,
                target_domain="domain:legal",
                reason_code="cross_access_requires_approval",
            ),
        )
    )
    approvals = tuple(approval_repo.list_requests())
    approvals_before = tuple(repo_request.id for repo_request in approvals)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Real Phase 10.44 memory/knowledge projection (canonical inputs)
    # ─────────────────────────────────────────────────────────────────────────
    store = InMemoryKnowledgeStore()
    item_study = KnowledgeItem(
        id="item:uni:study_capacity",
        statement="Daily 4-hour focused study capacity with scheduled breaks",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(value=0.92),
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=CUR_FROM,
            valid_until=CUR_TO,
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
            kind=TemporalScopeKind.INTERVAL,
            valid_from=CUR_FROM,
            valid_until=CUR_TO,
        ),
        created_at=NOW,
        updated_at=NOW,
        metadata={"applicable_domains": ["oppositions"]},
    )
    store.save_item(item_study)
    store.save_item(item_goal)
    store_items_before = {item.id: item.statement for item in store.list_items()}

    prop_repo = InMemoryKnowledgeUpdateRepository()
    prop_engine = KnowledgeUpdateProposalEngine(repository=prop_repo)
    proposal_context = KnowledgeUpdateContext(
        context_id="ctx-prop-045", agent_run_id="run-045", goal_id="goal-045"
    )

    def _checkpoint(**kwargs):  # type: ignore[no-untyped-def]
        checkpoint = MagicMock(spec=list(kwargs.keys()))
        for key, value in kwargs.items():
            setattr(checkpoint, key, value)
        return checkpoint

    real_checkpoint = _checkpoint(
        checkpoint_id="chk-rel-045",
        dependencies=[item_goal.id],
    )
    real_proposal = prop_engine.create_proposal(
        context=proposal_context,
        checkpoints=(real_checkpoint,),
    )
    assert real_proposal.relations, "Phase 9 LINK path produced no relation"
    assert real_proposal.relations[0].relation_type == "depends_on"
    assert real_proposal.relations[0].target_item_id == item_goal.id

    # Real Phase 10.18 view over current and superseded/expired references.
    ref_uni = DomainMemoryReference(
        reference_id="ref:uni:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id=item_study.id,
        domain_id="domain:university",
        applicable_domains=("domain:university",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from=CUR_FROM.isoformat(),
            valid_to=CUR_TO.isoformat(),
        ),
        evidence_ids=("ev:uni:1",),
        resource_ids=("res:uni:1",),
    )
    ref_health = DomainMemoryReference(
        reference_id="ref:health:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:health:regimen",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from=CUR_FROM.isoformat(),
            valid_to=CUR_TO.isoformat(),
        ),
        evidence_ids=("ev:health:1",),
        resource_ids=("res:health:1",),
    )
    ref_history = DomainMemoryReference(
        reference_id="ref:uni:history",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:uni:study_capacity:history",
        domain_id="domain:university",
        applicable_domains=("domain:university",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from=CUR_FROM.isoformat(),
            valid_to=CUR_TO.isoformat(),
        ),
        superseded_by_id=ref_uni.reference_id,
        evidence_ids=("ev:history:1",),
        resource_ids=("res:history:1",),
    )
    ref_invalidated = DomainMemoryReference(
        reference_id="ref:health:invalidated",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:health:invalidated",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from=OLD_FROM.isoformat(),
            valid_to=OLD_TO.isoformat(),
            invalidated=True,
            invalidation_reason="superseded",
        ),
        evidence_ids=("ev:invalidated:1",),
        resource_ids=("res:invalidated:1",),
    )
    ref_expired = DomainMemoryReference(
        reference_id="ref:opp:expired",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:opp:expired",
        domain_id="domain:oppositions",
        applicable_domains=("domain:oppositions",),
        temporal=DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.INTERVAL,
            valid_from=OLD_FROM.isoformat(),
            valid_to=OLD_TO.isoformat(),
            expires_at=OLD_TO.isoformat(),
        ),
        evidence_ids=("ev:expired:1",),
        resource_ids=("res:expired:1",),
    )
    all_references = (
        ref_uni,
        ref_health,
        ref_history,
        ref_invalidated,
        ref_expired,
    )

    def _read_decision(
        decision_id: str, source_domain_id: str
    ) -> DomainMemoryPermissionDecisionSnapshot:
        return DomainMemoryPermissionDecisionSnapshot(
            decision_id=decision_id,
            allowed=True,
            capabilities=("READ",),
            target_domain_id="domain:university",
            source_domain_id=source_domain_id,
        )

    permissions = (
        _read_decision("perm:read:uni", "domain:university"),
        _read_decision("perm:read:health", "domain:health"),
        _read_decision("perm:read:opp", "domain:oppositions"),
        _read_decision("perm:read:life", "domain:life-plan"),
    )
    mem_req = DomainMemoryViewRequest(
        request_id="mem-req-045",
        primary_domain=DomainId("university"),
        supporting_domains=(
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        candidates=all_references,
        permission_decision_ids=tuple(p.decision_id for p in permissions),
        temporal_reference=NOW.isoformat(),
        resolution_reference_id=resolution.id,
    )
    mem_inv = DomainMemoryReferenceInventory(
        references=all_references,
        permission_decisions=permissions,
    )
    view_resolver = DefaultDomainMemoryViewResolver()
    view = view_resolver.resolve(mem_req, mem_inv)
    view_validator = DefaultDomainMemoryIntegrationValidator()
    view_validation = view_validator.validate_view(view, mem_req, mem_inv)
    assert view_validation.is_valid is True
    view_selected_ids = {r.reference_id for r in view.selected_references}
    assert {"ref:uni:1", "ref:health:1"} == view_selected_ids
    excluded_ids = {d.reference_id for d in view.excluded_decisions}
    assert _STALE_REFERENCE_IDS <= excluded_ids

    mem_knowledge_req = DomainMemoryKnowledgeProjectionRequest(
        request_id="proj-req-045",
        primary_domain=DomainId("university"),
        supporting_domains=(
            DomainId("health"),
            DomainId("oppositions"),
            DomainId("life-plan"),
        ),
        memory_view_id=view.view_id,
        memory_view_digest=view.digest,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        permission_decision_ids=tuple(p.decision_id for p in permissions),
        temporal_reference=NOW.isoformat(),
        requested_capabilities=(
            DomainMemoryKnowledgeProjectionCapability.SHARED_IDENTITIES,
        ),
    )
    mem_knowledge_integrator = DefaultDomainMemoryKnowledgeIntegrator()
    mem_projection = mem_knowledge_integrator.project(
        mem_knowledge_req,
        memory_request=mem_req,
        view=view,
        memory_inventory=mem_inv,
        inventory=DomainMemoryKnowledgeInventory(
            relations=tuple(store.list_relations()),
            contradictions=tuple(store.list_contradictions()),
        ),
        resolution=resolution,
        composition=composition,
    )
    assert isinstance(mem_projection, DomainMemoryKnowledgeProjection)
    assert set(mem_projection.selected_reference_ids) == view_selected_ids
    assert set(mem_projection.selected_reference_ids).isdisjoint(_STALE_REFERENCE_IDS)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Canonical Phase 10.16 presentation state (visible plan content)
    # ─────────────────────────────────────────────────────────────────────────
    items = (
        _make_item(
            "finding:045:study:capacity",
            DomainPresentationItemType.FINDING,
            source_order=0,
            domain_ids=(_PRIMARY, "domain:health"),
            confidence=0.9,
            requires_provenance=True,
        ),
        _make_item(
            "finding:045:career:plan",
            DomainPresentationItemType.FINDING,
            source_order=1,
            domain_ids=("domain:life-plan", _PRIMARY),
            confidence=0.95,
            requires_provenance=True,
        ),
        _make_item(
            contradiction_id,
            DomainPresentationItemType.CONTRADICTION,
            source_order=2,
            domain_ids=(_PRIMARY, "domain:health"),
        ),
        _make_item(
            "approval-req:045:operation:1",
            DomainPresentationItemType.APPROVAL,
            source_order=3,
            domain_ids=(_PRIMARY,),
        ),
        _make_item(
            "workflow:045:review",
            DomainPresentationItemType.WORKFLOW,
            source_order=4,
            domain_ids=(_PRIMARY,),
        ),
        _make_item(
            real_proposal.proposal_id,
            DomainPresentationItemType.MEMORY_PROPOSAL,
            source_order=5,
            domain_ids=(_PRIMARY,),
        ),
        # Hidden/denied content is never a visible display slot.
        _make_item(
            "finding:045:legal:denied",
            DomainPresentationItemType.FINDING,
            source_order=6,
            domain_ids=("domain:legal",),
            visible=False,
            confidence=0.99,
            requires_provenance=True,
        ),
    )
    presentation = _make_presentation_with_items(
        items,
        composition_id=_COMPOSITION_ID,
        plan_id="presentation-plan:045",
        request_id="presentation-request:045",
        approval_refs=("approval-req:045:operation:1",),
        workflow_refs=("workflow:045:review",),
        memory_proposal_refs=(real_proposal.proposal_id,),
    )
    assert isinstance(presentation, DomainPresentationPlan)

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Real Phase 10.15 permission state and selector delegation wiring
    # ─────────────────────────────────────────────────────────────────────────
    permission_registry = DomainPermissionRegistry()
    permission_registry.register(
        DomainPermissionPolicy(
            policy_id="policy:university:045",
            domain_id=_PRIMARY,
            version="1.0.0",
            allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
            allow_cross_domain_access=True,
            allowed_target_domains=("domain:health",),
            allowed_sensitivity_levels=(SensitivityLevel.CONFIDENTIAL,),
        )
    )
    permission_registry.register(
        DomainPermissionPolicy(
            policy_id="policy:health:045",
            domain_id="domain:health",
            version="1.0.0",
            allowed_capabilities=(PermissionCapability.DOMAIN_CROSS_ACCESS,),
            allow_inbound_cross_domain_access=True,
            allowed_source_domains=(_PRIMARY,),
            allowed_sensitivity_levels=(SensitivityLevel.CONFIDENTIAL,),
        )
    )
    permission_resolver = DomainPermissionResolver(permission_registry)

    # The real facade integrator delegates selector intents only to the real
    # resolver and the real Phase 10.15 evaluator.
    collaborators = _make_collaborators()
    collaborators["interface_integrator"] = DefaultDomainInterfaceIntegrator(
        resolver=resolver,
        permission_resolver=permission_resolver,
    )
    api = DefaultDomainAPI(**collaborators)

    def _cross_permission_request(
        target_domain: str,
    ) -> CrossDomainPermissionRequest:
        return CrossDomainPermissionRequest(
            request_id=f"permission-request:045:{target_domain.removeprefix('domain:')}",
            source_domain=_PRIMARY,
            target_domain=target_domain,
            reason="supporting domain application through domain selector",
            actor_id="actor:045",
            session_id=_SESSION_ID,
            sensitivity_level=SensitivityLevel.CONFIDENTIAL,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 8: Connected positive projection through DefaultDomainAPI
    # ─────────────────────────────────────────────────────────────────────────
    request = DomainInterfaceProjectionRequest(
        request_id="interface-request:045",
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        session_reference_id=_SESSION_ID,
    )

    def project_through_domain_api() -> DomainInterfaceProjection:
        return api.project_interface(
            request,
            resolution=resolution,
            composition=composition,
            presentation=presentation,
            session=session,
            memory_knowledge=mem_projection,
            memory_knowledge_request=mem_knowledge_req,
            registry=registry,
            observability_report=observability_report,
            cross_domain_result=result,
            cross_domain_snapshot=snapshot,
            approvals=approvals,
        )

    projection = project_through_domain_api()

    # All five views are present and bound to the same canonical authority.
    assert projection.resolution_reference_id == resolution.id
    assert projection.composition_reference_id == composition.id
    assert projection.session_reference_id == _SESSION_ID
    assert projection.conversational is not None
    assert projection.selector is not None
    assert projection.domain_center is not None
    assert projection.cross_domain is not None
    assert projection.review_center is not None
    assert isinstance(projection, DomainInterfaceProjection)

    conversational: ConversationalDomainView = projection.conversational
    assert conversational.primary_domain == _PRIMARY
    assert set(conversational.supporting_domains) <= supporting_slugs
    assert "domain:health" in conversational.supporting_domains
    assert conversational.source_refs == (
        "finding:045:study:capacity",
        "finding:045:career:plan",
    )
    assert conversational.contradiction_refs == (contradiction_id,)
    assert conversational.approval_refs == ("approval-req:045:operation:1",)
    assert conversational.workflow_refs == ("workflow:045:review",)
    assert conversational.memory_proposal_refs == (real_proposal.proposal_id,)
    assert conversational.question_refs == ()
    assert conversational.warning_refs == ()
    # MAJOR-02 remediation: the supplied canonical cross-domain result id is
    # surfaced, never suppressed.
    assert conversational.result_refs == (result.id,)
    assert conversational.confidence == 0.9
    assert conversational.status is DomainInterfaceStatus.READY

    selector: DomainSelectorView = projection.selector
    assert selector.primary_domain == _PRIMARY
    assert selector.supporting_domains == tuple(
        str(d) for d in resolution.supporting_domains
    )
    assert selector.reason_refs == tuple(
        dict.fromkeys(reason.code for reason in resolution.reasons)
    )
    assert selector.requires_clarification is False
    assert selector.status is DomainInterfaceStatus.READY

    domain_center: DomainCenterView = projection.domain_center
    center_by_id = {entry.domain_id: entry for entry in domain_center.domains}
    assert len(center_by_id) == 6
    university_entry = center_by_id["domain:university"]
    assert university_entry.status == "active"
    assert university_entry.enabled is True
    assert university_entry.metric_refs == ("domain.operations",)
    assert university_entry.error_refs == ("error:uni:storage:1",)
    assert university_entry.update_status == "unknown"

    cross_domain: CrossDomainInterfaceView = projection.cross_domain
    assert cross_domain.primary_domain == _PRIMARY
    assert set(cross_domain.supporting_domains) == supporting_slugs
    assert cross_domain.transfer_refs == ("transfer:health:university:1",)
    assert cross_domain.dependency_refs == (
        "dependency:university:health:requires",
        "dependency:university:oppositions:informs",
    )
    assert cross_domain.conflict_refs == (contradiction_id,)
    assert cross_domain.consolidated_result_ref == result.id
    assert cross_domain.status is DomainInterfaceStatus.READY

    review_center: DomainReviewCenterView = projection.review_center
    review_by_ref = {item.review_ref: item for item in review_center.items}
    assert set(review_by_ref) == {
        "approval-req:045:cross:1",
        "approval-req:045:operation:1",
    }
    assert review_by_ref["approval-req:045:operation:1"].category == (
        "operation_approval"
    )
    assert review_by_ref["approval-req:045:operation:1"].state == "pending"
    assert review_by_ref["approval-req:045:operation:1"].domain_id == _PRIMARY
    assert review_by_ref["approval-req:045:operation:1"].operation_ref == (
        "operation:045:assess"
    )
    assert review_by_ref["approval-req:045:operation:1"].workflow_ref == (
        "workflow:045:review"
    )
    assert review_by_ref["approval-req:045:cross:1"].category == ("cross_domain_access")
    assert review_by_ref["approval-req:045:cross:1"].state == "pending"
    assert review_by_ref["approval-req:045:cross:1"].session_ref == _SESSION_ID

    # Deterministic projection: content digest survives serialization and a
    # second projection of the same canonical inputs is byte-identical.
    serialized = projection.to_dict()
    assert projection.content_digest
    assert (
        DomainInterfaceProjection.from_dict(serialized).content_digest
        == projection.content_digest
    )
    second_projection = project_through_domain_api()
    assert second_projection.to_dict() == serialized
    assert second_projection.content_digest == projection.content_digest

    # No raw/payload field of canonical content can leak into the projection.
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
    assert not (set(serialized) & forbidden_keys)
    assert "statement" not in json.dumps(serialized)
    # The denied domain is disclosed nowhere except the Domain Center lifecycle
    # record (which surfaces installed-but-disabled registry state verbatim).
    interactive_views = (conversational, selector, cross_domain, review_center)
    assert all(
        "domain:legal" not in json.dumps(view.to_dict()) for view in interactive_views
    )
    assert not (_STALE_REFERENCE_IDS & set(serialized.keys()))
    assert all(stale not in json.dumps(serialized) for stale in _STALE_REFERENCE_IDS)

    # No projection call mutated registry, approvals, proposal or store.
    assert _registry_records_state() == registry_before
    assert tuple(r.id for r in approval_repo.list_requests()) == approvals_before
    assert approval_repo.list_requests() == approvals
    assert {i.id: i.statement for i in store.list_items()} == store_items_before

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 1: resolution/composition mismatch fails closed
    # ─────────────────────────────────────────────────────────────────────────
    mismatched_request = DomainInterfaceProjectionRequest(
        request_id="interface-request:045:mismatch",
        resolution_reference_id=resolution.id,
        composition_reference_id="composition:other",
        session_reference_id=_SESSION_ID,
    )
    with pytest.raises(DomainInterfaceAuthorityError):
        api.project_interface(
            mismatched_request,
            resolution=resolution,
            composition=composition,
        )
    with pytest.raises(DomainInterfaceAuthorityError):
        api.project_interface(
            request,
            resolution=resolution,
            composition=dataclasses.replace(
                composition, id="composition:other", resolution_id="res:other"
            ),
        )
    with pytest.raises(DomainInterfaceAuthorityError):
        api.project_interface(
            dataclasses.replace(
                mismatched_request, composition_reference_id=_COMPOSITION_ID
            ),
            resolution=dataclasses.replace(
                resolution, id="res:other", context_id="res-ctx-other"
            ),
            composition=composition,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 2 + 5: denied and approval-required supporting-domain applications
    # ─────────────────────────────────────────────────────────────────────────
    legal_permission_request = _cross_permission_request("domain:legal")
    legal_decision = permission_resolver.resolve_cross_domain(legal_permission_request)
    assert isinstance(legal_decision, CrossDomainPermissionDecision)
    denied_intent = DomainInterfaceIntent(
        intent_id="intent:045:add:legal",
        kind=DomainInterfaceIntentKind.ADD_SUPPORTING,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        target_domain="domain:legal",
        session_reference_id=_SESSION_ID,
        reason="interface request to add denied supporting domain",
    )
    denied_result = api.submit_interface_intent(
        intent=denied_intent,
        resolution=resolution,
        composition=composition,
        resolution_context=res_context,
        permission_request=legal_permission_request,
    )
    assert isinstance(denied_result, DomainInterfaceIntentResult)
    assert denied_result.accepted is False
    assert denied_result.status is DomainInterfaceStatus.BLOCKED
    assert denied_result.reason_code == legal_decision.reasons[0]
    # The denied domain is neither authorized nor disclosed by the projection.
    assert "domain:legal" not in conversational.supporting_domains
    assert all(item.domain_id != "domain:legal" for item in review_center.items)
    assert "transfer:legal:university:1" not in cross_domain.transfer_refs

    health_permission_request = _cross_permission_request("domain:health")
    health_decision = permission_resolver.resolve_cross_domain(
        health_permission_request
    )
    assert isinstance(health_decision, CrossDomainPermissionDecision)
    pending_intent = DomainInterfaceIntent(
        intent_id="intent:045:add:health",
        kind=DomainInterfaceIntentKind.ADD_SUPPORTING,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        target_domain="domain:health",
        session_reference_id=_SESSION_ID,
        reason="interface request to add authorized supporting domain",
    )
    pending_result = api.submit_interface_intent(
        intent=pending_intent,
        resolution=resolution,
        composition=composition,
        resolution_context=res_context,
        permission_request=health_permission_request,
    )
    assert isinstance(pending_result, DomainInterfaceIntentResult)
    assert pending_result.accepted is False
    assert pending_result.status is DomainInterfaceStatus.PENDING
    # Pending approval state remains pending across the whole connected flow.
    assert review_by_ref["approval-req:045:operation:1"].state == "pending"
    assert review_by_ref["approval-req:045:cross:1"].state == "pending"

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 3 + 12: lifecycle statuses preserved; no update authority claimed
    # ─────────────────────────────────────────────────────────────────────────
    legal_entry = center_by_id["domain:legal"]
    assert legal_entry.status == "disabled"
    assert legal_entry.enabled is False
    assert legal_entry.update_status == "unknown"
    assert legal_entry.status != "active"
    finance_entry = center_by_id["domain:finance"]
    assert finance_entry.status == "degraded"
    assert finance_entry.status != "active"
    assert finance_entry.enabled is True
    assert finance_entry.update_status == "unknown"
    assert all(entry.update_status == "unknown" for entry in domain_center.domains)

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 4: selector privilege escalation is rejected
    # ─────────────────────────────────────────────────────────────────────────
    escalation_intent = DomainInterfaceIntent(
        intent_id="intent:045:select:legal",
        kind=DomainInterfaceIntentKind.SELECT_PRIMARY,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        target_domain="domain:legal",
        session_reference_id=_SESSION_ID,
        reason="interface request to escalate selection to a non-explicit domain",
    )
    with pytest.raises(DomainInterfaceAuthorityError):
        api.submit_interface_intent(
            intent=escalation_intent,
            resolution=resolution,
            composition=composition,
            resolution_context=res_context,
        )
    mismatched_evidence_intent = DomainInterfaceIntent(
        intent_id="intent:045:add:escalation",
        kind=DomainInterfaceIntentKind.ADD_SUPPORTING,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        target_domain="domain:health",
        session_reference_id=_SESSION_ID,
        reason="interface request with mismatched permission evidence",
    )
    with pytest.raises(DomainInterfaceAuthorityError):
        api.submit_interface_intent(
            intent=mismatched_evidence_intent,
            resolution=resolution,
            composition=composition,
            resolution_context=res_context,
            permission_request=legal_permission_request,
        )
    # A legitimate explicit select-primary intent still only reports the real
    # resolver outcome; it never mutates canonical authority.
    legitimate_intent = DomainInterfaceIntent(
        intent_id="intent:045:select:university",
        kind=DomainInterfaceIntentKind.SELECT_PRIMARY,
        resolution_reference_id=resolution.id,
        composition_reference_id=composition.id,
        target_domain="domain:university",
        session_reference_id=_SESSION_ID,
        reason="interface request confirming the resolved primary domain",
    )
    legitimate_result = api.submit_interface_intent(
        intent=legitimate_intent,
        resolution=resolution,
        composition=composition,
        resolution_context=res_context,
    )
    assert isinstance(legitimate_result, DomainInterfaceIntentResult)
    assert legitimate_result.accepted is True
    assert legitimate_result.status is DomainInterfaceStatus.READY

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 6 + 7: proposal/contradiction preservation and store immutability
    # ─────────────────────────────────────────────────────────────────────────
    assert conversational.memory_proposal_refs == (real_proposal.proposal_id,)
    fetched_proposal = prop_repo.get_proposal(real_proposal.proposal_id)
    assert fetched_proposal is not None
    assert fetched_proposal.relations
    assert fetched_proposal.relations[0].relation_type == "depends_on"
    assert prop_repo.get_decision(real_proposal.proposal_id) is None
    assert prop_repo.get_result(real_proposal.proposal_id) is None
    assert cross_domain.conflict_refs == (contradiction_id,)
    assert snapshot.contradictions[0].resolved is False, (
        "canonical contradiction remained unresolved"
    )
    assert {i.id: i.statement for i in store.list_items()} == store_items_before

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 8: confidence never strengthened
    # ─────────────────────────────────────────────────────────────────────────
    # The projection confidence is the minimum over effectively visible items
    # only; a hidden high-confidence item never strengthens it.
    visible_finding_confidences = sorted(
        item.confidence
        for item in presentation.item_refs
        if item.item_type is DomainPresentationItemType.FINDING
        and item.visible
        and item.confidence is not None
    )
    hidden_confidences = [
        item.confidence
        for item in presentation.item_refs
        if not item.visible and item.confidence is not None
    ]
    assert visible_finding_confidences == [0.9, 0.95]
    assert hidden_confidences and max(hidden_confidences) == 0.99
    assert conversational.confidence == min(visible_finding_confidences)
    assert conversational.confidence == 0.9
    assert conversational.confidence < max(hidden_confidences)

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 9: superseded/invalidated/expired knowledge cannot re-enter
    # ─────────────────────────────────────────────────────────────────────────
    assert not (_STALE_REFERENCE_IDS & view_selected_ids)
    assert set(mem_projection.selected_reference_ids).isdisjoint(_STALE_REFERENCE_IDS)
    assert all(
        stale not in json.dumps(projection.to_dict()) for stale in _STALE_REFERENCE_IDS
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 10: dependency/correlation never relabelled as causation
    # ─────────────────────────────────────────────────────────────────────────
    assert cross_domain.dependency_refs == (
        "dependency:university:health:requires",
        "dependency:university:oppositions:informs",
    )
    assert tuple(dep.kind for dep in snapshot.dependencies) == (
        "requires",
        "informs",
    )
    assert result.dependencies == snapshot.dependencies
    # The interface copies canonical kinds verbatim into refs; "causes" is
    # never fabricated anywhere in the cross-domain view payload.
    assert all(":causes" not in ref for ref in cross_domain.dependency_refs)
    assert "causes" not in json.dumps(cross_domain.to_dict()).lower()

    # ─────────────────────────────────────────────────────────────────────────
    # Branch 11: partial composition remains partial
    # ─────────────────────────────────────────────────────────────────────────
    partial_composition = dataclasses.replace(
        composition, status=DomainCompositionStatus.PARTIAL
    )
    partial_projection = api.project_interface(
        request,
        resolution=resolution,
        composition=partial_composition,
        presentation=presentation,
        session=session,
        memory_knowledge=mem_projection,
        memory_knowledge_request=mem_knowledge_req,
        registry=registry,
        observability_report=observability_report,
        cross_domain_result=result,
        cross_domain_snapshot=snapshot,
        approvals=approvals,
    )
    assert partial_projection.conversational is not None
    assert partial_projection.conversational.status is DomainInterfaceStatus.PARTIAL
    assert partial_projection.cross_domain is not None
    assert partial_projection.cross_domain.status is DomainInterfaceStatus.PARTIAL
    assert partial_projection.conversational.status is not DomainInterfaceStatus.READY

    # Canonical authority remained unchanged by every projection and intent.
    assert _registry_records_state() == registry_before
    assert tuple(r.id for r in approval_repo.list_requests()) == approvals_before
    assert approval_repo.list_requests() == approvals
    assert {i.id: i.statement for i in store.list_items()} == store_items_before
    assert prop_repo.get_decision(real_proposal.proposal_id) is None
    assert prop_repo.get_result(real_proposal.proposal_id) is None
    assert (
        resolution.to_dict()
        == DefaultDomainResolver(
            fallback_domain=DomainId("general"),
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=3, supporting_margin=100.0
            ),
            clock=lambda: NOW,
            id_factory=lambda: _RESOLUTION_ID,
        )
        .resolve(res_context)
        .to_dict()
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Step 9: Emit stable acceptance marker
    # ─────────────────────────────────────────────────────────────────────────
    print("AT-DP-045=PASS")
