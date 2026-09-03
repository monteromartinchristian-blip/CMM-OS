"""Phase 10.40 — AT-DP-040 connected acceptance test.

DP-040 — Canonical Domain-to-Cognitive Integration Boundary.

Connects the full Domain-to-Cognitive flow using real canonical components:
DomainResolutionContext
→ DefaultDomainResolver
→ DefaultDomainComposer
→ DefaultDomainProfileResolver
→ DefaultDomainResourceResolver
→ canonical Domain permission/trust decision
→ DomainCognitiveIntegrationRequest
→ DefaultDomainCognitiveIntegrator
→ ResourceAdapterRegistry
→ KnowledgeExtractorRegistry
→ InMemoryKnowledgeStore
→ KnowledgePackageBuilder
→ CognitiveValidator
→ ReasoningRuleRegistry
→ DefaultDomainRuleSelector
→ DefaultDomainRuleExecutor
→ DefaultReasoningRuleEngine
→ DomainPresentationItemRef
→ DefaultDomainPresentationPlanner
→ DomainTraceAssembler
→ DefaultDomainTraceReferenceValidator

Mocks are not used to replace accepted behavior. Real canonical components or
official in-memory implementations exercise the complete integrated pipeline.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive import (
    CognitiveValidator,
    Confidence,
    Contradiction,
    ContradictionSeverity,
    ExistingResourceAdapter,
    InMemoryKnowledgeStore,
    KnowledgeBundle,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgePackage,
    KnowledgeStatus,
    MappingResourceAdapter,
    PlainTextKnowledgeExtractor,
    PlainTextResourceAdapter,
    ReasoningGap,
    ReasoningRuleResult,
    Resource,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceProvenance,
    ResourceSourceKind,
    ResourceTemporalScope,
    SensitivityLevel,
)
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
    DomainCognitiveResourceInput,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainReasoningDepth,
    DomainResourceResolutionStatus,
)
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import (
    DomainPermissionPolicy,
    DomainPermissionRequest,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.presentation_contracts import (
    DomainPresentationItemType,
    DomainPresentationRequest,
)
from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
from cmm.domains.profile_contracts import (
    DomainPresentationPolicy,
    DomainProfileDefinition,
    DomainProfileResolutionRequest,
    DomainTemporalPolicy,
    ResolvedDomainProfile,
)
from cmm.domains.profile_resolver import DefaultDomainProfileResolver
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionResource,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.resource_contracts import (
    DomainResourceContext,
    DomainResourceDefinition,
)
from cmm.domains.resource_resolver import DefaultDomainResourceResolver
from cmm.domains.rule_catalog import build_initial_reasoning_rule_catalog
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
    DomainTraceRole,
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from cmm.domains.university.definition import build_university_domain_definition

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
VALID_FROM = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
VALID_UNTIL = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)
OBSERVED_AT = datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc)
LAST_VERIFIED_AT = datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc)

ROOT = Path(__file__).resolve().parents[2]


class _Checkpointer:
    """Deterministic acceptance checkpoints."""

    def __init__(self) -> None:
        self.points: list[str] = []

    def checkpoint(self, name: str) -> None:
        self.points.append(name)


def test_at_dp040_connected_cognitive_integration() -> None:
    """Connected AT-DP-040 acceptance test exercising the full 21-point contract."""
    cp = _Checkpointer()

    # ── 1. Domain resolution & multi-domain composition ───────────────────
    res_context = DomainResolutionContext(
        id="res-ctx-040",
        user_input="University examination in Room 101 with medical accommodation",
        available_domains=(DomainId("university"), DomainId("health")),
        authorized_domains=(DomainId("university"), DomainId("health")),
        explicit_domains=(DomainId("university"),),
        active_domains=(),
        resources=(
            DomainResolutionResource(
                id="res-ref-040",
                resource_type="document",
                source="user",
                domain_ids=(DomainId("health"),),
            ),
        ),
        created_at=NOW,
    )
    domain_resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        scoring_policy=DomainScoringPolicy(
            max_supporting_domains=1, supporting_margin=100.0
        ),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-040",
    )
    resolution = domain_resolver.resolve(res_context)
    assert resolution.primary_domain == DomainId("university")
    assert resolution.supporting_domains == (DomainId("health"),)
    cp.checkpoint("01-domain-resolved")

    composer = DefaultDomainComposer(
        id_factory=lambda: "composition-040",
        clock=lambda: NOW,
    )
    composition = composer.compose(
        resolution,
        (build_university_domain_definition(), build_health_domain_definition()),
    )
    assert composition.status in {
        DomainCompositionStatus.COMPOSED,
        DomainCompositionStatus.PARTIAL,
    }
    assert composition.primary_domain == DomainId("university")
    assert composition.supporting_domains == (DomainId("health"),)
    cp.checkpoint("02-domain-composed")

    # ── 2. Real profile resolution ────────────────────────────────────────
    profile_resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-040",
        profile_id_factory=lambda: "resolved-profile-040",
        trace_id_factory=lambda: "prof-trace-040",
    )
    profile_resolution = profile_resolver.resolve(
        request=DomainProfileResolutionRequest(
            id="prof-req-040",
            primary_domain=DomainId("university"),
            supporting_domains=(DomainId("health"),),
        ),
        global_profile=DomainProfileDefinition(
            id="general.profile",
            domain_id=DomainId("general"),
            profile_name="GeneralProfile",
        ),
        primary_profile=DomainProfileDefinition(
            id="university.profile",
            domain_id=DomainId("university"),
            profile_name="UniversityProfile",
            required_rules=("university.deadline",),
            minimum_confidence=0.75,
            reasoning_depth=DomainReasoningDepth.STANDARD,
            maximum_questions=10,
            temporal_policy=DomainTemporalPolicy(
                require_current_information=True,
                maximum_age_seconds=86400,
            ),
            presentation_policy=DomainPresentationPolicy(
                include_provenance=True,
                preferred_section_order=(
                    "findings",
                    "gaps",
                    "contradictions",
                    "questions",
                ),
            ),
        ),
        supporting_profiles=(
            DomainProfileDefinition(
                id="health.profile",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
            ),
        ),
    )
    profile = profile_resolution.profile
    assert isinstance(profile, ResolvedDomainProfile)
    assert profile.primary_domain == DomainId("university")
    assert profile.supporting_domains == (DomainId("health"),)
    cp.checkpoint("03-profile-resolved")

    # ── 3. Canonical Domain resource resolution components ───────────────
    res_definition = DomainResourceDefinition(
        id="def-subject-guide-040",
        kind="subject_guide",
        domain_id=DomainId("university"),
        adapter="existing_resource",
        default_permissions=("resource.read",),
        default_sensitivity="internal",
    )
    res_context_item = DomainResourceContext(
        resource_id="res-exam-guide-040",
        kind="subject_guide",
        provenance=("academic-registry-01",),
        permissions=("resource.read",),
        temporal_scope={
            "valid_from": VALID_FROM,
            "valid_until": VALID_UNTIL,
            "observed_at": OBSERVED_AT,
            "last_verified_at": LAST_VERIFIED_AT,
        },
        sensitivity="internal",
    )
    resource_resolver = DefaultDomainResourceResolver(
        id_factory=lambda: "res-res-040", clock=lambda: NOW
    )

    # ── 4. Canonical Domain permission/trust decision ─────────────────────
    from cmm.agent_runtime.agent_security_enums import (
        SensitivityLevel as AgentSensitivityLevel,
    )
    from cmm.agent_runtime.domain_permission_contracts import PermissionOutcome

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-uni-040",
            domain_id="domain:university",
            version="1.0.0",
            allowed_capabilities=(PermissionCapability.RESOURCE_READ,),
            allowed_sensitivity_levels=(
                AgentSensitivityLevel.INTERNAL,
                AgentSensitivityLevel.PUBLIC,
            ),
        )
    )
    perm_resolver = DomainPermissionResolver(perm_registry)

    # Prove denied permission stops the resource/integration path
    denied_perm = perm_resolver.resolve(
        DomainPermissionRequest(
            request_id="perm-req-denied",
            action=PermissionCapability.FILE_MODIFY,
            domain_id="domain:university",
            actor_id="student-040",
            session_id="session-040",
        )
    )
    assert denied_perm.effective_permissions.decision is PermissionOutcome.DENY

    denied_res = resource_resolver.resolve(
        context=res_context_item,
        definitions=(res_definition,),
        requested_domains=(DomainId("university"),),
        request_permissions=("unauthorized.permission",),
    )
    assert len(denied_res.bindings) == 0
    assert len(denied_res.permission_denials) > 0
    cp.checkpoint("04-permission-denial-enforced")

    # Prove allowed permission proceeds
    allowed_perm = perm_resolver.resolve(
        DomainPermissionRequest(
            request_id="perm-req-allowed",
            action=PermissionCapability.RESOURCE_READ,
            domain_id="domain:university",
            resource_id=res_context_item.resource_id,
            sensitivity_level=AgentSensitivityLevel.INTERNAL,
            actor_id="student-040",
            session_id="session-040",
        )
    )
    assert allowed_perm.effective_permissions.decision is PermissionOutcome.ALLOW
    effective_permissions = ("resource.read",)
    cp.checkpoint("05-permission-allowed")

    # ── 5. Real resource resolution under allowed permissions ─────────────
    resource_resolution = resource_resolver.resolve(
        context=res_context_item,
        definitions=(res_definition,),
        requested_domains=(DomainId("university"),),
        request_permissions=effective_permissions,
    )
    assert resource_resolution.status == DomainResourceResolutionStatus.RESOLVED
    assert len(resource_resolution.bindings) == 1
    binding = resource_resolution.bindings[0]
    cp.checkpoint("06-resource-resolved")

    # ── 5. Configure Phase 8 components & seed prior knowledge ────────────
    store = InMemoryKnowledgeStore()
    prior_fact = KnowledgeItem(
        id="prior-fact-040",
        statement="All registered students must take examinations in designated rooms.",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.61, source="academic-handbook"),
        resource_id=binding.resource_id,
        created_at=NOW,
        updated_at=NOW,
    )
    prior_contrasting = KnowledgeItem(
        id="prior-fact-040-alt",
        statement="Examinations may be taken remotely upon prior approval.",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.70, source="academic-handbook-amendment"),
        resource_id=binding.resource_id,
        created_at=NOW,
        updated_at=NOW,
    )
    store.save_item(prior_fact)
    store.save_item(prior_contrasting)

    prior_contradiction = Contradiction(
        id="prior-contradiction-040",
        item_a_id=prior_fact.id,
        item_b_id=prior_contrasting.id,
        severity=ContradictionSeverity.MEDIUM,
        created_at=NOW,
    )
    store.save_contradiction(prior_contradiction)

    # Capture store state snapshot before integration
    store_records_before = {
        k: (r.record_type, dict(r.payload)) for k, r in store._records.items()
    }
    cp.checkpoint("07-prior-knowledge-seeded")

    # ── 6. Setup registries and canonical integrator ──────────────────────
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(PlainTextResourceAdapter())
    adapter_registry.register(MappingResourceAdapter())
    adapter_registry.register(ExistingResourceAdapter())

    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())

    rule_catalog = build_initial_reasoning_rule_catalog()

    integrator = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=store,
        rule_registry=rule_catalog,
        cognitive_validator=CognitiveValidator(),
        rule_selector=DefaultDomainRuleSelector(clock=lambda: NOW),
        rule_executor=DefaultDomainRuleExecutor(clock=lambda: NOW),
        clock=lambda: NOW,
    )
    cp.checkpoint("08-integrator-configured")

    # ── 7. Build request with statement and explicit question ─────────────
    raw_payload = (
        "The university examination is scheduled for October 15 in Room 101.\n"
        "Which room is the exam in?"
    )
    canonical_res = Resource(
        id=binding.resource_id,
        domain="domain:university",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.LOCAL_FILE,
        content=raw_payload,
        provenance=ResourceProvenance(
            source_id=binding.resource_id,
            source_type=ResourceSourceKind.LOCAL_FILE,
            retrieved_at=NOW,
        ),
        reliability=Confidence(0.9),
        temporal_scope=ResourceTemporalScope(),
        sensitivity=SensitivityLevel.INTERNAL,
        permissions=(
            ResourcePermission(
                allowed_operations=(
                    ResourcePermissionOperation.READ,
                    ResourcePermissionOperation.INFER,
                )
            ),
        ),
        integrity=ResourceIntegrityStatus.VERIFIED,
    )
    resource_input = DomainCognitiveResourceInput(
        resolution=resource_resolution,
        binding=binding,
        source=ResourceInput(
            id=binding.resource_id,
            payload=canonical_res,
            source_kind=ResourceSourceKind.LOCAL_FILE,
            sensitivity=SensitivityLevel.INTERNAL,
        ),
        extractor_name="plain_text",
    )
    integration_request = DomainCognitiveIntegrationRequest(
        request_id="int-req-040",
        resolution_context_id=res_context.id,
        resolution_result_id=resolution.id,
        objective=res_context.user_input,
        composition=composition,
        profile=profile,
        resources=(resource_input,),
        actor_id="student-040",
        session_id="session-040",
        effective_permissions=effective_permissions,
        global_mandatory_rules=("global.distinguish_fact_inference_hypothesis",),
        requested_rule_ids=("university.deadline",),
        metadata={"academic_year": "2026-2027"},
    )
    cp.checkpoint("09-integration-request-built")

    # ── 8. Execute integration ────────────────────────────────────────────
    result = integrator.integrate(integration_request)
    cp.checkpoint("10-integration-executed")

    # ═══════════════════════════════════════════════════════════════════════
    # Required assertions 1-21
    # ═══════════════════════════════════════════════════════════════════════

    # 1. Domain specialization affects canonical cognitive inputs/configuration.
    assert result.reasoning_context.primary_domain == "domain:university"
    assert result.reasoning_context.supporting_domains == ("domain:health",)
    assert result.reasoning_context.active_domains == (
        "domain:university",
        "domain:health",
    )
    assert result.reasoning_context.metadata["domain_profile_id"] == profile.id
    assert result.reasoning_context.metadata["domain_composition_id"] == composition.id
    assert (
        result.reasoning_context.metadata["minimum_confidence"]
        == profile.minimum_confidence
    )
    assert (
        result.reasoning_context.metadata["reasoning_depth"]
        == profile.reasoning_depth.value
    )
    assert (
        result.reasoning_context.metadata["maximum_questions"]
        == profile.maximum_questions
    )

    # 2. Cognitive ownership remains Phase 8.
    assert isinstance(result.rule_result.rule_results[0], ReasoningRuleResult)
    assert isinstance(result.knowledge_package, KnowledgePackage)
    assert all(isinstance(r, Resource) for r in result.adapted_resources)
    assert all(isinstance(b, KnowledgeBundle) for b in result.extracted_bundles)

    # 3. Global mandatory rule executes before Domain rule.
    assert tuple(r.definition.id for r in result.rule_plan.selected_rules) == (
        "global.distinguish_fact_inference_hypothesis",
        "university.deadline",
    )
    assert result.rule_result.applied_rule_ids == (
        "global.distinguish_fact_inference_hypothesis",
        "university.deadline",
    )

    # 4. Accepted Domain resource becomes canonical Phase 8 Resource.
    adapted_resource = result.adapted_resources[0]
    assert type(adapted_resource) is Resource
    assert adapted_resource.id == binding.resource_id

    # 5. Provenance is preserved.
    assert adapted_resource.provenance.source_id == binding.resource_id
    assert adapted_resource.provenance.metadata["domain_binding_id"] == binding.id
    assert (
        adapted_resource.provenance.metadata["domain_definition_id"]
        == binding.definition_id
    )
    assert (
        adapted_resource.provenance.metadata["domain_provenance"] == binding.provenance
    )
    assert (
        adapted_resource.provenance.metadata["domain_source_priority"]
        == binding.source_priority
    )

    # 6. Sensitivity is preserved.
    assert adapted_resource.sensitivity == SensitivityLevel.INTERNAL
    assert adapted_resource.sensitivity == binding.sensitivity
    assert result.reasoning_context.effective_sensitivity == "internal"

    # 7. Temporal semantics are preserved.
    assert adapted_resource.temporal_scope.valid_from == VALID_FROM
    assert adapted_resource.temporal_scope.valid_until == VALID_UNTIL
    assert adapted_resource.temporal_scope.observed_at == OBSERVED_AT
    assert adapted_resource.temporal_scope.last_verified_at == LAST_VERIFIED_AT

    # 8. Binding reliability is canonical Confidence.
    assert isinstance(adapted_resource.reliability, Confidence)
    assert adapted_resource.reliability.value == binding.reliability
    assert adapted_resource.reliability.source == "domain_resource_binding"
    assert adapted_resource.reliability.reasons == (binding.id,)

    # 9. Extracted statement remains canonical unverified knowledge.
    statement_item = next(
        item
        for bundle in result.extracted_bundles
        for item in bundle.items
        if item.kind is not KnowledgeKind.QUESTION
    )
    assert statement_item.status == KnowledgeStatus.UNVERIFIED

    # 10. Explicit question follows CandidateKind.QUESTION → KnowledgeKind.QUESTION → open_questions.
    question_item = next(
        item
        for bundle in result.extracted_bundles
        for item in bundle.items
        if item.kind is KnowledgeKind.QUESTION
    )
    assert question_item.statement == "Which room is the exam in?"
    assert question_item.statement in result.extracted_bundles[0].open_questions
    assert any(
        item.ref_id == question_item.id
        and item.item_type is DomainPresentationItemType.QUESTION
        and item.requires_user_interaction is True
        and item.pending is True
        for item in result.presentation_items
    )

    # 11. Canonical ReasoningGap passes through real rule execution.
    deadline_gap = next(
        gap for gap in result.rule_result.gaps if gap.code == "DEADLINE_INFORMATION_GAP"
    )
    assert isinstance(deadline_gap, ReasoningGap)
    assert deadline_gap.rule_id == "university.deadline"
    assert any(
        item.item_type is DomainPresentationItemType.GAP and "gap" in item.ref_id
        for item in result.presentation_items
    )

    # 12. Canonical Contradiction semantics remain Phase 8-owned.
    assert any(
        c.id == "prior-contradiction-040"
        for c in result.knowledge_package.contradictions
    )
    assert any(
        c.id == "prior-contradiction-040"
        for c in result.reasoning_context.contradictions
    )
    assert isinstance(result.reasoning_context.contradictions[0], Contradiction)

    # 13. Domain profile minimum_confidence does not overwrite evidence confidence.
    seeded_item = next(
        item
        for item in result.reasoning_context.knowledge_items
        if item.id == "prior-fact-040"
    )
    assert seeded_item.confidence.value == 0.61
    assert profile.minimum_confidence > 0.61
    assert seeded_item.confidence.value != profile.minimum_confidence

    # 14. CognitiveValidator genuinely executes canonical validation.
    assert len(result.validation_results) >= 3  # package, resource, items
    executed_rules = {
        rule_id
        for val_result in result.validation_results
        for rule_id in val_result.validated_rules
    }
    assert "cognitive.knowledge_package" in executed_rules
    assert "cognitive.provenance" in executed_rules
    assert "cognitive.temporality" in executed_rules
    assert "cognitive.epistemology" in executed_rules

    # 15. Presentation is planned through DefaultDomainPresentationPlanner.
    presentation_plan = DefaultDomainPresentationPlanner().plan(
        DomainPresentationRequest(
            request_id="pres-plan-req-040",
            upstream_result_id=result.rule_result.id,
            composition_id=composition.id,
            policy_id=profile.id,
            presentation=composition.presentation,
            policy=profile.presentation_policy,
            items=result.presentation_items,
            primary_domain_id=str(composition.primary_domain),
            supporting_domain_ids=tuple(str(d) for d in composition.supporting_domains),
        )
    )
    assert presentation_plan.item_refs == result.presentation_items
    assert question_item.id in presentation_plan.question_refs
    assert (
        next(
            item
            for item in presentation_plan.item_refs
            if item.item_type is DomainPresentationItemType.QUESTION
        ).confidence
        == question_item.confidence.value
    )

    # 16. Domain Trace is assembled with references only.
    trace_refs = replace(
        result.trace_references,
        presentation_plan_ids=(presentation_plan.plan_id,),
    )
    trace_request = DomainTraceAssemblyRequest(
        request_id="trace-req-040",
        primary_domain=DomainId("university"),
        supporting_domains=(DomainId("health"),),
        contributions=(
            DomainTraceContribution(
                DomainId("university"),
                DomainTraceRole.PRIMARY,
                (
                    DomainTraceReference(
                        profile.id,
                        DomainTraceReferenceKind.PROFILE,
                        DomainId("university"),
                    ),
                    DomainTraceReference(
                        resource_resolution.id,
                        DomainTraceReferenceKind.RESOURCE_RESOLUTION,
                        DomainId("university"),
                    ),
                    DomainTraceReference(
                        result.rule_plan.id,
                        DomainTraceReferenceKind.RULE_PLAN,
                        DomainId("university"),
                    ),
                    DomainTraceReference(
                        result.rule_result.id,
                        DomainTraceReferenceKind.RULE_RESULT,
                        DomainId("university"),
                    ),
                ),
            ),
            DomainTraceContribution(
                DomainId("health"),
                DomainTraceRole.SUPPORTING,
                (),
            ),
        ),
        references=trace_refs,
        started_at=NOW,
        completed_at=NOW,
    )
    trace = DomainTraceAssembler().assemble(trace_request)
    inventory = DomainTraceReferenceInventory(
        references=trace.all_references(),
        domain_results=trace.domain_results,
        cross_domain_results=trace.references.cross_domain_results,
        expected_primary_domain="domain:university",
        expected_supporting_domains=("domain:health",),
        resolution_result_domains=DomainTraceDomainSelection(
            resolution.id,
            DomainId("university"),
            (DomainId("health"),),
        ),
        composition_domains=DomainTraceDomainSelection(
            composition.id,
            DomainId("university"),
            (DomainId("health"),),
        ),
    )
    trace_validation = DefaultDomainTraceReferenceValidator().validate(trace, inventory)
    assert trace_validation.valid

    # 17. No hidden reasoning is copied.
    trace_dict = trace.to_dict()
    forbidden_substrings = (
        "chain_of_thought",
        "reasoning_text",
        "scratchpad",
        "hidden_trace",
        "internal_reasoning",
    )
    trace_str = str(trace_dict).lower()
    for token in forbidden_substrings:
        assert token not in trace_str

    # 18. InMemoryKnowledgeStore is unchanged by integration.
    store_records_after = {
        k: (r.record_type, dict(r.payload)) for k, r in store._records.items()
    }
    assert store_records_before == store_records_after

    # 19. cmm.cognitive → cmm.domains imports remain absent.
    cognitive_dir = ROOT / "cmm" / "cognitive"
    for py_path in sorted(cognitive_dir.rglob("*.py")):
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("cmm.domains"), (
                    f"Forbidden import in {py_path}: {mod}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("cmm.domains"), (
                        f"Forbidden import in {py_path}: {alias.name}"
                    )

    # 20. Agent Runtime is not required.
    integration_file = ROOT / "cmm" / "domains" / "cognitive_integration.py"
    contracts_file = ROOT / "cmm" / "domains" / "cognitive_integration_contracts.py"
    for path in (integration_file, contracts_file):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith("cmm.agent_runtime"), (
                    f"Agent runtime in {path}: {mod}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("cmm.agent_runtime"), (
                        f"Agent runtime in {path}: {alias.name}"
                    )

    # 21. CrossDomainEngine is not the Phase 10.40 owner.
    for path in (integration_file, contracts_file):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "cross_domain_engine" not in mod, f"CrossDomain in {path}: {mod}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "cross_domain_engine" not in alias.name, (
                        f"CrossDomain in {path}: {alias.name}"
                    )

    cp.checkpoint("21-all-assertions-verified")
    assert cp.points[-1] == "21-all-assertions-verified"
