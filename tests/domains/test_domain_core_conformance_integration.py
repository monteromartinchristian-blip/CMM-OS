"""Phase 10.51 — connected core conformance integration.

Real-component conformance across the canonical Domain Intelligence seams. No
chain of isolated mocks: every check drives production owners through their real
public interfaces, using the official first-party Project bootstrap as the
representative connected journey.

Seams proven here (extended by later Phase 10.51 tasks in this same module):

    canonical first-party DomainDefinition
      -> canonical pack/bootstrap/registry
      -> canonical resolution
      -> canonical composition
      -> canonical permission restriction
      -> resource / operation / workflow availability
      -> Cognitive / Knowledge Package projection
      -> canonical privacy decision
      -> safe Domain Trace reference evidence
      -> memory/knowledge proposal/reference integration
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.cognitive import (
    CognitiveValidator,
    Confidence,
    Evidence,
    EvidenceKind,
    ExistingResourceAdapter,
    InMemoryKnowledgeStore,
    InMemoryReasoningRuleRegistry,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    PlainTextKnowledgeExtractor,
    Resource,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
)
from cmm.cognitive.privacy import (
    PrivacyOperation,
    PrivacyOperationContext,
    ProcessingLocation,
    evaluate_privacy_operation,
    resolve_effective_privacy_metadata,
)
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveResourceInput,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainOperationStatus,
    DomainReasoningDepth,
    DomainResolutionStatus,
    DomainResourceResolutionStatus,
)
from cmm.domains.errors import DomainOperationRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.life_plan.catalog import LIFE_PLAN_DOMAIN_ID
from cmm.domains.memory_contracts import (
    DomainMemoryApprovalDecisionSnapshot,
    DomainMemoryApprovalRequestSnapshot,
    DomainMemoryPermissionDecisionSnapshot,
    DomainMemoryReferenceInventory,
    DomainMemoryTraceSnapshot,
    DomainMemoryViewSnapshot,
)
from cmm.domains.memory_validation import DomainMemoryValidationCode
from cmm.domains.memory_view import DefaultDomainMemoryViewResolver
from cmm.domains.operation_availability import (
    DomainOperationAvailabilityContext,
    DomainOperationAvailabilityResolver,
)
from cmm.domains.permission_contracts import DomainPermissionRequest
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.privacy_policy_contracts import project_domain_privacy_metadata
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)
from cmm.domains.project.bootstrap import (
    ProjectDomainBootstrap,
    build_standard_project_domain_bootstrap,
)
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.knowledge_package import build_project_knowledge_package_schema
from cmm.domains.project.memory import (
    build_project_memory_binding,
    build_project_memory_proposal,
    build_project_memory_view_request,
)
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.project.privacy import build_project_privacy_policy
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceResolution,
)
from cmm.domains.rule_execution import DefaultDomainRuleExecutor
from cmm.domains.rule_selection import DefaultDomainRuleSelector
from cmm.domains.trace_assembler import DomainTraceAssembler
from cmm.domains.trace_contracts import (
    DomainTraceAssemblyRequest,
    DomainTraceContribution,
    DomainTraceDomainSelection,
    DomainTraceReference,
    DomainTraceReferenceInventory,
    DomainTraceReferenceKind,
    DomainTraceReferences,
    DomainTraceRole,
    DomainTraceValidationCode,
    PrivacyDecisionTraceEvidence,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.enums import WorkflowAvailabilityStatus

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)

# ── Connected-journey helpers (reuse the official bootstrap, never rewire) ────


def connected_bootstrap() -> ProjectDomainBootstrap:
    """The official Project bootstrap, with the primary Domain enabled."""
    bootstrap = build_standard_project_domain_bootstrap()
    bootstrap.domain_registry.enable(PROJECT_DOMAIN_ID)
    return bootstrap


def resolve_project(
    bootstrap: ProjectDomainBootstrap,
    *,
    context_id: str = "ctx:conformance:1",
    explicit: tuple[str, ...] = (PROJECT_DOMAIN_ID,),
):
    """Resolve through the canonical DefaultDomainResolver."""
    available = tuple(definition.id for definition in bootstrap.domain_registry.list())
    context = DomainResolutionContext(
        id=context_id,
        user_input="plan my project milestones",
        explicit_domains=tuple(DomainId.from_str(slug) for slug in explicit),
        available_domains=available,
        authorized_domains=available,
    )
    return bootstrap.resolver.resolve(context)


def compose_resolution(bootstrap: ProjectDomainBootstrap, resolution):
    """Compose through the canonical DefaultDomainComposer."""
    definitions = tuple(
        bootstrap.domain_registry.get_required(str(domain_id))
        for domain_id in (resolution.primary_domain, *resolution.supporting_domains)
    )
    return DefaultDomainComposer().compose(resolution, definitions)


def operation_execute_request(
    *,
    request_id: str = "req:conformance:op",
    operation_id: str = "project.review_status",
    operation_version: str = "1.0.0",
) -> DomainPermissionRequest:
    return DomainPermissionRequest(
        request_id=request_id,
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id=PROJECT_DOMAIN_ID,
        actor_id="actor:conformance",
        session_id="session:conformance",
        operation_id=operation_id,
        operation_version=operation_version,
    )


# ── Block 3/6/7: registry -> resolution -> composition are connected ──────────


def test_project_core_path_uses_canonical_registry_resolution_and_composition():
    bootstrap = connected_bootstrap()

    assert bootstrap.domain_registry.contains(PROJECT_DOMAIN_ID)
    assert bootstrap.resolver.fallback_domain == DomainId.from_str("domain:general")

    resolution = resolve_project(bootstrap)
    assert resolution.status is DomainResolutionStatus.RESOLVED
    assert resolution.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)

    composition = compose_resolution(bootstrap, resolution)
    assert composition.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert composition.status is DomainCompositionStatus.COMPOSED
    # Composition carries the canonical effective surfaces, not a parallel truth.
    assert composition.operations
    assert composition.rules
    assert composition.resources


def test_resolution_selects_exactly_one_primary_domain():
    bootstrap = connected_bootstrap()
    resolution = resolve_project(bootstrap)
    assert resolution.primary_domain is not None
    # supporting membership is explicit and bounded
    assert isinstance(resolution.supporting_domains, tuple)
    assert resolution.primary_domain not in resolution.supporting_domains


# ── Block 14: permissions restrict authority, never grant it ──────────────────


def test_permission_resolver_allows_declared_and_denies_prohibited():
    bootstrap = connected_bootstrap()
    resolver = DomainPermissionResolver(bootstrap.permission_registry)

    allowed = resolver.resolve(operation_execute_request(request_id="req:allow"))
    assert allowed.effective_permissions.decision is PermissionOutcome.ALLOW

    prohibited = resolver.resolve(
        DomainPermissionRequest(
            request_id="req:publication",
            action=PermissionCapability.PUBLICATION,
            domain_id=PROJECT_DOMAIN_ID,
            actor_id="actor:conformance",
            session_id="session:conformance",
        )
    )
    assert prohibited.effective_permissions.decision is PermissionOutcome.DENY


def test_supporting_domain_permission_intersection_is_most_restrictive():
    bootstrap = connected_bootstrap()
    resolver = DomainPermissionResolver(bootstrap.permission_registry)
    request = operation_execute_request(request_id="req:cross")

    baseline = resolver.resolve(request, supporting_domains=(LIFE_PLAN_DOMAIN_ID,))
    assert baseline.effective_permissions.decision is PermissionOutcome.ALLOW

    # Downgrade only the supporting Domain's policy; primary is unchanged.
    supporting_policy = bootstrap.permission_registry.active_for_domain(
        LIFE_PLAN_DOMAIN_ID
    )
    narrowed_registry = DomainPermissionRegistry()
    narrowed_registry.register(
        bootstrap.permission_registry.active_for_domain(PROJECT_DOMAIN_ID)
    )
    narrowed_registry.register(
        dataclasses.replace(
            supporting_policy,
            allowed_capabilities=tuple(
                capability
                for capability in supporting_policy.allowed_capabilities
                if capability is not PermissionCapability.OPERATION_EXECUTE
            ),
        )
    )
    narrowed_resolver = DomainPermissionResolver(narrowed_registry)

    restricted = narrowed_resolver.resolve(
        operation_execute_request(request_id="req:cross"),
        supporting_domains=(LIFE_PLAN_DOMAIN_ID,),
    )
    assert restricted.effective_permissions.decision is PermissionOutcome.DENY


def test_authority_downgrade_removing_permission_fails_closed():
    """Adversarial: drop OPERATION_EXECUTE from the canonical Project policy.

    A fresh registry/resolver re-evaluates from current authority; the stale
    ALLOW must not survive (STALE_AUTHORITY_REUSED=NO,
    DOWNGRADED_AUTHORITY=FAIL_CLOSED).
    """
    bootstrap = connected_bootstrap()
    request = operation_execute_request(request_id="req:downgrade")

    before = DomainPermissionResolver(bootstrap.permission_registry).resolve(request)
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    project_policy = bootstrap.permission_registry.active_for_domain(PROJECT_DOMAIN_ID)
    downgraded = DomainPermissionRegistry()
    downgraded.register(
        dataclasses.replace(
            project_policy,
            allowed_capabilities=tuple(
                capability
                for capability in project_policy.allowed_capabilities
                if capability is not PermissionCapability.OPERATION_EXECUTE
            ),
        )
    )

    after = DomainPermissionResolver(downgraded).resolve(
        operation_execute_request(request_id="req:downgrade")
    )
    assert after.effective_permissions.decision is PermissionOutcome.DENY


# ── Block 12: declared operations are not executable by declaration alone ─────


def test_declared_project_operation_without_implementation_stays_unavailable():
    """No injected implementation => the canonical registry fails closed."""
    bootstrap = build_standard_project_domain_bootstrap()
    declared = {
        definition.operation_id for definition in build_project_operation_definitions()
    }
    assert "project.review_status" in declared
    try:
        bootstrap.operation_registry.get_implementation(
            "project.review_status", "1.0.0"
        )
    except DomainOperationRegistryError as exc:
        assert "UNAVAILABLE" in str(exc)
    else:  # pragma: no cover - declaration alone must never be executable
        raise AssertionError("declared operation became executable without an impl")


def test_operation_availability_resolver_blocks_when_permission_removed():
    from cmm.agent_runtime.enums import ApprovalRequestStatus

    definition = next(
        item
        for item in build_project_operation_definitions()
        if item.operation_id == "project.modify_code"
    )
    assert definition.required_permissions
    base_context = DomainOperationAvailabilityContext(
        primary_domain_id=PROJECT_DOMAIN_ID,
        supporting_domain_ids=(),
        granted_permissions=tuple(definition.required_permissions),
        denied_permissions=(),
        available_resources=tuple(definition.required_resources),
        capabilities=("execute", "rollback", "transaction"),
        available_validation_policy_ids=(definition.validation_policy_id,),
        available_rollback_policy_ids=(definition.rollback_policy_id,),
        approval_status=ApprovalRequestStatus.APPROVED,
        approval_fingerprint="fingerprint",
        request_fingerprint="fingerprint",
    )
    resolver = DomainOperationAvailabilityResolver()
    granted = resolver.resolve(definition, base_context)
    assert granted.status is DomainOperationStatus.AVAILABLE

    revoked = resolver.resolve(
        definition,
        dataclasses.replace(base_context, granted_permissions=()),
    )
    assert revoked.status is DomainOperationStatus.BLOCKED
    assert revoked.required_permissions == tuple(definition.required_permissions)
    assert any("permission" in entry.reason_code for entry in revoked.trace_entries)


# ── Block 13: workflow authority uses the shared engine and denies closed ─────


def test_project_workflow_resolution_denies_when_a_required_permission_is_denied():
    bootstrap = connected_bootstrap()
    workflow = next(
        item
        for item in bootstrap.workflow_registry.list_for_domain(PROJECT_DOMAIN_ID)
        if item.required_permissions
    )
    denied_permission = workflow.required_permissions[0]

    permissive = resolve_domain_workflow(
        workflow,
        DomainWorkflowContext(
            PROJECT_DOMAIN_ID,
            available_permissions=frozenset(workflow.required_permissions),
            denied_permissions=frozenset(),
            available_resources=frozenset(workflow.required_resources),
            available_operations=frozenset(
                node.operation_id
                for node in workflow.nodes
                if node.operation_id is not None
            ),
            known_domain_ids=frozenset({workflow.domain_id}),
        ),
    )
    assert permissive.status is not WorkflowAvailabilityStatus.BLOCKED

    blocked = resolve_domain_workflow(
        workflow,
        DomainWorkflowContext(
            PROJECT_DOMAIN_ID,
            available_permissions=frozenset(workflow.required_permissions),
            denied_permissions=frozenset({denied_permission}),
            available_resources=frozenset(workflow.required_resources),
            known_domain_ids=frozenset({workflow.domain_id}),
        ),
    )
    assert blocked.status is WorkflowAvailabilityStatus.BLOCKED


# ── Blocks 28/17: Cognitive + Knowledge Package projection ────────────────────


def _cognitive_resource_input() -> DomainCognitiveResourceInput:
    payload = Resource(
        id="resource-1",
        domain=PROJECT_DOMAIN_ID,
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content="The project plan is stable.",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="source-1",
            retrieved_at=NOW,
        ),
        reliability=Confidence(0.99, source="adapter"),
        temporal_scope=ResourceTemporalScope(
            content_created_at=NOW, observed_at=NOW, ingested_at=NOW
        ),
        sensitivity=SensitivityLevel.INTERNAL,
        permissions=(
            ResourcePermission(
                allowed_operations=(
                    ResourcePermissionOperation.READ,
                    ResourcePermissionOperation.INFER,
                )
            ),
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    binding = DomainResourceBinding(
        id="binding-1",
        resource_id="resource-1",
        definition_id="definition-1",
        domain_id=DomainId("project"),
        adapter="existing_resource",
        provenance=("domain-source-1",),
        sensitivity=SensitivityLevel.INTERNAL,
        temporal_scope={
            "valid_from": NOW,
            "valid_until": NOW,
            "observed_at": NOW,
            "last_verified_at": NOW,
        },
        source_priority=17,
        reliability=0.73,
    )
    resolution = DomainResourceResolution(
        id="resolution-1",
        resource_id=binding.resource_id,
        status=DomainResourceResolutionStatus.RESOLVED,
        trace_id="resolution-trace-1",
        resolved_at=NOW,
        bindings=(binding,),
    )
    return DomainCognitiveResourceInput(
        resolution=resolution,
        binding=binding,
        source=ResourceInput(
            id=binding.resource_id,
            source_kind=ResourceSourceKind.USER_INPUT,
            payload=payload,
            sensitivity=binding.sensitivity,
        ),
        extractor_name="plain_text",
    )


def _project_profile() -> ResolvedDomainProfile:
    return ResolvedDomainProfile(
        id="profile-1",
        primary_domain=DomainId("project"),
        supporting_domains=(),
        profile_names=("ProjectProfile",),
        required_rules=(),
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=None,
        priority_resource_kinds=(),
        prohibited_resource_kinds=(),
        minimum_confidence=0.8,
        reasoning_depth=DomainReasoningDepth.DEEP,
        allowed_inferences=None,
        prohibited_inferences=(),
        maximum_questions=3,
        escalation_rules=(),
        prohibited_actions=(),
        question_policy=DomainQuestionPolicy(),
        presentation_policy=DomainPresentationPolicy(),
        memory_policy=DomainMemoryPolicy(),
        temporal_policy=DomainTemporalPolicy(),
        production_policy=DomainProductionPolicy(),
        permissions=None,
        modifications=(),
        trace_id="profile-trace-1",
        resolved_at=NOW,
    )


def test_cognitive_integration_projects_a_canonical_knowledge_package():
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(ExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())
    store = InMemoryKnowledgeStore()
    store.save_item(
        KnowledgeItem(
            id="item-1",
            statement="Review the project plan.",
            kind=KnowledgeKind.OBSERVATION,
            confidence=Confidence(0.95, source="source-1"),
            resource_id="resource-1",
            evidence=(
                Evidence(
                    resource_id="resource-1",
                    fragment="The project plan is stable.",
                    confidence=Confidence(0.95, source="source-1"),
                    kind=EvidenceKind.DIRECT_QUOTE,
                ),
            ),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    integrator = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=store,
        rule_registry=InMemoryReasoningRuleRegistry(),
        cognitive_validator=CognitiveValidator(),
        rule_selector=DefaultDomainRuleSelector(clock=lambda: NOW),
        rule_executor=DefaultDomainRuleExecutor(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    composition = DomainComposition(
        id="composition-1",
        resolution_id="resolution-result-1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("project"),
        composed_at=NOW,
    )
    request = DomainCognitiveIntegrationRequest(
        request_id="request-1",
        resolution_context_id="resolution-context-1",
        resolution_result_id="resolution-result-1",
        objective="Review project plan",
        composition=composition,
        profile=_project_profile(),
        resources=(_cognitive_resource_input(),),
        actor_id="actor-1",
        session_id="session-1",
        effective_permissions=("resource:read", "resource:infer"),
        knowledge_package_schema=build_project_knowledge_package_schema(),
    )

    items_before = [item.serialize() for item in store.list_items()]
    result = integrator.integrate(request)

    # Canonical Phase 8 representation, projected through the real schema.
    assert isinstance(result.knowledge_package, KnowledgePackage)
    assert result.trace_references.knowledge_package_ids == (
        result.knowledge_package.id,
    )
    # The cognitive truth stays singular: the Domain integration never writes it.
    assert [item.serialize() for item in store.list_items()] == items_before


def test_first_party_knowledge_package_schemas_compose_with_a_sensitivity_floor():
    from tests.domains.domain_core_conformance_support import (
        load_first_party_definitions,
    )

    schemas = tuple(
        definition.knowledge_package_schema
        for definition in load_first_party_definitions()
        if definition.knowledge_package_schema is not None
    )
    assert len(schemas) == 12
    effective = compose_domain_knowledge_package_schemas(schemas)
    # Composition narrows: the effective floor is at least SENSITIVE.
    assert effective.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert "objective" in effective.required_sections


# ── Blocks 16/28: privacy decision -> reference-only Domain Trace evidence ────


def _project_privacy_evidence() -> PrivacyDecisionTraceEvidence:
    metadata = project_domain_privacy_metadata(
        build_project_privacy_policy(),
        processing_location=ProcessingLocation.REMOTE,
    )
    effective = resolve_effective_privacy_metadata(metadata).effective
    decision = evaluate_privacy_operation(
        effective,
        PrivacyOperation.PROCESS_REMOTE,
        PrivacyOperationContext(processing_location=ProcessingLocation.REMOTE, at=NOW),
    )
    return PrivacyDecisionTraceEvidence.from_privacy_decision(
        domain_id=PROJECT_DOMAIN_ID,
        operation=PrivacyOperation.PROCESS_REMOTE,
        decision=decision,
    )


def test_privacy_decision_evidence_is_reference_only_with_no_raw_leak():
    evidence = _project_privacy_evidence()
    reference = evidence.to_reference()

    assert isinstance(reference, DomainTraceReference)
    assert reference.kind is DomainTraceReferenceKind.PRIVACY_DECISION
    assert set(reference.to_dict()) == {"ref_id", "kind", "domain_id"}

    serialized = repr(evidence.to_dict())
    for forbidden in (
        "reasons",
        "privacy_metadata",
        "prompt",
        "payload",
        "credential",
        "token",
        "secret",
    ):
        assert forbidden not in serialized


def test_domain_trace_validation_accepts_bound_privacy_evidence_and_rejects_fake():
    evidence = _project_privacy_evidence()
    reference = evidence.to_reference()
    global_references = (
        DomainTraceReference(
            "resolution-context:1", DomainTraceReferenceKind.RESOLUTION_CONTEXT
        ),
        DomainTraceReference(
            "resolution-result:1", DomainTraceReferenceKind.RESOLUTION_RESULT
        ),
        DomainTraceReference("composition:1", DomainTraceReferenceKind.COMPOSITION),
    )

    request = DomainTraceAssemblyRequest(
        request_id="request:privacy-1",
        primary_domain=PROJECT_DOMAIN_ID,
        contributions=(
            DomainTraceContribution(
                PROJECT_DOMAIN_ID, DomainTraceRole.PRIMARY, (reference,)
            ),
        ),
        references=DomainTraceReferences(
            "resolution-context:1", "resolution-result:1", "composition:1"
        ),
        started_at=NOW,
        completed_at=NOW.replace(second=1),
    )
    trace = DomainTraceAssembler().assemble(request)
    inventory = DomainTraceReferenceInventory(
        references=(*global_references, reference),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", PROJECT_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", PROJECT_DOMAIN_ID
        ),
        privacy_decisions=(evidence,),
    )

    validator = DefaultDomainTraceReferenceValidator()
    assert validator.validate(trace, inventory).valid

    fake = DomainTraceReference(
        ref_id="privacy-decision:000000000000000000000000",
        kind=DomainTraceReferenceKind.PRIVACY_DECISION,
        domain_id=PROJECT_DOMAIN_ID,
    )
    tampered = DomainTraceAssembler().assemble(
        DomainTraceAssemblyRequest(
            request_id="request:privacy-1",
            primary_domain=PROJECT_DOMAIN_ID,
            contributions=(
                DomainTraceContribution(
                    PROJECT_DOMAIN_ID, DomainTraceRole.PRIMARY, (fake,)
                ),
            ),
            references=DomainTraceReferences(
                "resolution-context:1", "resolution-result:1", "composition:1"
            ),
            started_at=NOW,
            completed_at=NOW.replace(second=1),
        )
    )
    rejected = validator.validate(tampered, inventory)
    assert not rejected.valid
    assert DomainTraceValidationCode.PRIVACY_DECISION_PAIRING_MISMATCH in rejected.codes


# ── Blocks 17/28: memory proposal/reference integration fails closed ──────────


def test_memory_proposal_binding_is_proposal_only_and_fails_closed_on_downgrade():
    proposal = build_project_memory_proposal(
        proposal_id="prop:1", affected_reference_ids=("ref:project:x",)
    )
    assert proposal.requires_confirmation is True

    permission = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:propose:1",
        allowed=True,
        capabilities=("PROPOSE",),
        target_domain_id=PROJECT_DOMAIN_ID,
        source_domain_id=PROJECT_DOMAIN_ID,
    )
    request = build_project_memory_view_request(
        request_id="req:mem:1",
        trace_id="trace:1",
        permission_decision_ids=("perm:propose:1",),
    )
    granted_inventory = DomainMemoryReferenceInventory(
        permission_decisions=(permission,), proposals=(proposal,)
    )
    view = DefaultDomainMemoryViewResolver().resolve(request, granted_inventory)

    view_snapshot = DomainMemoryViewSnapshot(
        view_id=view.view_id,
        request_id=request.request_id,
        primary_domain=view.primary_domain,
        trace_id="trace:1",
        view_digest=view.content_digest,
    )
    trace_snapshot = DomainMemoryTraceSnapshot(
        trace_id="trace:1", primary_domain=PROJECT_DOMAIN_ID
    )
    approval_request = DomainMemoryApprovalRequestSnapshot(
        request_id="appr:1", proposal_id="prop:1"
    )
    approval_decision = DomainMemoryApprovalDecisionSnapshot(
        decision_id="appd:1", request_id="appr:1", approved=True
    )
    binding = build_project_memory_binding(
        proposal=proposal,
        view=view,
        trace_id="trace:1",
        permission_decision_ids=("perm:propose:1",),
        approval_request_ids=("appr:1",),
        approval_decision_ids=("appd:1",),
    )

    from cmm.domains.memory_validation import (
        DefaultDomainMemoryIntegrationValidator,
    )

    validator = DefaultDomainMemoryIntegrationValidator()
    authorized_inventory = DomainMemoryReferenceInventory(
        permission_decisions=(permission,),
        proposals=(proposal,),
        views=(view_snapshot,),
        traces=(trace_snapshot,),
        approval_requests=(approval_request,),
        approval_decisions=(approval_decision,),
    )
    assert validator.validate_binding(binding, authorized_inventory).is_valid

    revoked = DomainMemoryPermissionDecisionSnapshot(
        decision_id="perm:propose:1",
        allowed=False,
        capabilities=(),
        target_domain_id=PROJECT_DOMAIN_ID,
        source_domain_id=PROJECT_DOMAIN_ID,
    )
    downgraded_inventory = DomainMemoryReferenceInventory(
        permission_decisions=(revoked,),
        proposals=(proposal,),
        views=(view_snapshot,),
        traces=(trace_snapshot,),
        approval_requests=(approval_request,),
        approval_decisions=(approval_decision,),
    )
    downgraded = validator.validate_binding(binding, downgraded_inventory)
    assert downgraded.is_valid is False
    assert downgraded.code is DomainMemoryValidationCode.INVALID_PERMISSION_DENIED
