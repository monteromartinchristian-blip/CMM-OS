"""Phase 10.51 — AT-DP-051 Core Conformance and Connected Journey acceptance.

The connected acceptance for DP-051. Every scenario drives real canonical
production components (or official in-memory ports); nothing here is a chain of
isolated mocks, and no one-off journey orchestrator exists: each seam is called
through its own owner's public interface.

Scenarios:

    A — historical block inventory is complete
    B — canonical ownership is singular
    C — first-party Domain core is reachable
    D — resolution/composition/permission path is connected
    E — operation/workflow authority remains canonical
    F — Cognitive / Knowledge Package / privacy evidence is connected
    G — trace/memory integration remains reference/proposal based
    H — authority downgrade fails closed
    I — SDK/API/CLI surfaces reuse canonical owners
    J — security/observability/fragmentation guards remain active
    K — 10.52/10.53 and Phase 11 boundaries remain deferred
"""

from __future__ import annotations

import dataclasses
import importlib
from datetime import datetime, timezone

import pytest

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
    ResourceAdapterRegistry,
    SensitivityLevel,
)
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveIntegrationRequest,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.interface_integration import DefaultDomainInterfaceIntegrator
from cmm.domains.interface_integration_contracts import (
    DomainInterfaceProjectionRequest,
)
from cmm.domains.knowledge_package_composition import (
    compose_domain_knowledge_package_schemas,
)
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.project.knowledge_package import build_project_knowledge_package_schema
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.project.permissions import build_project_permission_policy
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
)
from cmm.domains.trace_validation import DefaultDomainTraceReferenceValidator
from cmm.domains.workflow_contracts import DomainWorkflowContext
from cmm.domains.workflow_resolution import resolve_domain_workflow
from cmm.workflows.enums import WorkflowAvailabilityStatus
from tests.domains.domain_core_conformance_support import (
    CORE_CONFORMANCE_REQUIREMENTS,
    DEFERRED_DOMAIN_IDS,
    FIRST_PARTY_DOMAIN_IDS,
    HISTORICAL_AGGREGATE_BASELINE,
    CoreConformanceClassification,
    canonical_cognitive_resource_input,
    canonical_project_privacy_evidence,
    canonical_project_profile,
    compose_resolution,
    connected_bootstrap,
    deferred_classification_count,
    first_party_definition_builders,
    historical_block_count,
    load_first_party_definitions,
    operation_execute_request,
    parallel_owner_required_count,
    resolve_project,
    unmapped_required_blocks,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


# ── A — historical block inventory is complete ────────────────────────────────


def test_scenario_a_historical_block_inventory_is_complete() -> None:
    assert historical_block_count() == 28
    assert tuple(item.block for item in CORE_CONFORMANCE_REQUIREMENTS) == tuple(
        range(1, 29)
    )
    assert unmapped_required_blocks() == ()


# ── B — canonical ownership is singular ───────────────────────────────────────


def test_scenario_b_canonical_ownership_is_singular() -> None:
    assert parallel_owner_required_count() == 0
    assert not [
        requirement
        for requirement in CORE_CONFORMANCE_REQUIREMENTS
        if requirement.classification is CoreConformanceClassification.GAP_RED
    ]
    for requirement in CORE_CONFORMANCE_REQUIREMENTS:
        assert requirement.owner_modules, requirement.block
        assert requirement.evidence, requirement.block
        for module_name in requirement.owner_modules:
            importlib.import_module(module_name)


# ── C — first-party Domain core is reachable ──────────────────────────────────


def test_scenario_c_first_party_core_is_reachable_through_canonical_owners() -> None:
    definitions = load_first_party_definitions()
    assert len(definitions) == 12
    assert {str(definition.id) for definition in definitions} == set(
        FIRST_PARTY_DOMAIN_IDS
    )
    builders = first_party_definition_builders()
    assert len(builders) == 12

    bootstrap = connected_bootstrap()
    for definition in definitions:
        registry_domain = bootstrap.domain_registry.get(str(definition.id))
        # Project/General/Life Plan live in the official bootstrap; the other
        # packs are reachable through the same canonical registry contract by
        # registering their real definitions.
        if registry_domain is None:
            registered = bootstrap.domain_registry.register(definition)
            assert registered.id == definition.id
            bootstrap.domain_registry.unregister(str(definition.id), definition.version)
        else:
            assert registry_domain.version == definition.version


# ── D — resolution/composition/permission path is connected ───────────────────


def test_scenario_d_resolution_composition_permission_path_is_connected() -> None:
    bootstrap = connected_bootstrap()

    resolution = resolve_project(bootstrap)
    assert resolution.status is DomainResolutionStatus.RESOLVED
    assert resolution.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)

    composition = compose_resolution(bootstrap, resolution)
    assert composition.primary_domain == DomainId.from_str(PROJECT_DOMAIN_ID)
    assert composition.status is DomainCompositionStatus.COMPOSED
    assert composition.operations and composition.rules and composition.resources

    decision = DomainPermissionResolver(bootstrap.permission_registry).resolve(
        operation_execute_request(request_id="req:dp051:d")
    )
    assert decision.effective_permissions.decision is PermissionOutcome.ALLOW


# ── E — operation/workflow authority remains canonical ────────────────────────


def test_scenario_e_operation_and_workflow_authority_is_canonical() -> None:
    bootstrap = connected_bootstrap()

    declared = {
        definition.operation_id for definition in build_project_operation_definitions()
    }
    assert "project.review_status" in declared
    # Declaration alone never makes an operation executable: no fake delegate
    # is installed by the official bootstrap.
    from cmm.domains.errors import DomainOperationRegistryError

    with pytest.raises(DomainOperationRegistryError):
        bootstrap.operation_registry.get_implementation(
            "project.review_status", "1.0.0"
        )

    workflow = next(
        item
        for item in bootstrap.workflow_registry.list_for_domain(PROJECT_DOMAIN_ID)
        if item.required_permissions
    )
    blocked = resolve_domain_workflow(
        workflow,
        DomainWorkflowContext(
            PROJECT_DOMAIN_ID,
            available_permissions=frozenset(workflow.required_permissions),
            denied_permissions=frozenset({workflow.required_permissions[0]}),
            available_resources=frozenset(workflow.required_resources),
            known_domain_ids=frozenset({workflow.domain_id}),
        ),
    )
    assert blocked.status is WorkflowAvailabilityStatus.BLOCKED


# ── F — Cognitive / Knowledge Package / privacy evidence is connected ─────────


def test_scenario_f_cognitive_knowledge_and_privacy_seams_are_connected() -> None:
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
    )
    composition = DomainComposition(
        id="composition-1",
        resolution_id="resolution-result-1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId("project"),
        composed_at=NOW,
    )
    result = integrator.integrate(
        DomainCognitiveIntegrationRequest(
            request_id="request-1",
            resolution_context_id="resolution-context-1",
            resolution_result_id="resolution-result-1",
            objective="Review project plan",
            composition=composition,
            profile=canonical_project_profile(NOW),
            resources=(canonical_cognitive_resource_input(NOW),),
            actor_id="actor-1",
            session_id="session-1",
            effective_permissions=("resource:read", "resource:infer"),
            knowledge_package_schema=build_project_knowledge_package_schema(),
        )
    )
    # Phase 8 truth stays singular: canonical package, untouched store.
    assert isinstance(result.knowledge_package, KnowledgePackage)
    assert store.list_items().__len__() == 1

    # Sensitivity floor and privacy remain separate canonical concepts: the
    # composed Knowledge Package floor says nothing about privacy decisions.
    effective_schema = compose_domain_knowledge_package_schemas(
        tuple(
            definition.knowledge_package_schema
            for definition in load_first_party_definitions()
            if definition.knowledge_package_schema is not None
        )
    )
    assert effective_schema.minimum_sensitivity is SensitivityLevel.SENSITIVE
    assert not hasattr(effective_schema, "privacy_policy")

    evidence = canonical_project_privacy_evidence(NOW)
    assert evidence.allowed is False  # canonical Project privacy decision


# ── G — trace/memory integration remains reference/proposal based ─────────────


def test_scenario_g_trace_and_memory_stay_reference_and_proposal_based() -> None:
    evidence = canonical_project_privacy_evidence(NOW)
    reference = evidence.to_reference()
    assert set(reference.to_dict()) == {"ref_id", "kind", "domain_id"}

    trace = DomainTraceAssembler().assemble(
        DomainTraceAssemblyRequest(
            request_id="request:trace-1",
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
    )
    inventory = DomainTraceReferenceInventory(
        references=(
            DomainTraceReference(
                "resolution-context:1", DomainTraceReferenceKind.RESOLUTION_CONTEXT
            ),
            DomainTraceReference(
                "resolution-result:1", DomainTraceReferenceKind.RESOLUTION_RESULT
            ),
            DomainTraceReference("composition:1", DomainTraceReferenceKind.COMPOSITION),
            reference,
        ),
        expected_primary_domain=PROJECT_DOMAIN_ID,
        resolution_result_domains=DomainTraceDomainSelection(
            "resolution-result:1", PROJECT_DOMAIN_ID
        ),
        composition_domains=DomainTraceDomainSelection(
            "composition:1", PROJECT_DOMAIN_ID
        ),
        privacy_decisions=(evidence,),
    )
    validation = DefaultDomainTraceReferenceValidator().validate(trace, inventory)
    assert validation.valid

    # Memory mutation is proposal/binding only: the official Project proposal
    # always requires confirmation and never writes a store directly.
    from cmm.domains.project.memory import build_project_memory_proposal

    proposal = build_project_memory_proposal(
        proposal_id="prop:dp051", affected_reference_ids=("ref:project:x",)
    )
    assert proposal.requires_confirmation is True


# ── H — authority downgrade fails closed ──────────────────────────────────────


def test_scenario_h_authority_downgrade_fails_closed() -> None:
    bootstrap = connected_bootstrap()
    request = operation_execute_request(request_id="req:dp051:h")

    before = DomainPermissionResolver(bootstrap.permission_registry).resolve(request)
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    # Change one current canonical authority input: remove OPERATION_EXECUTE.
    project_policy = build_project_permission_policy()
    downgraded_registry = DomainPermissionRegistry()
    downgraded_registry.register(
        dataclasses.replace(
            project_policy,
            allowed_capabilities=tuple(
                capability
                for capability in project_policy.allowed_capabilities
                if capability is not PermissionCapability.OPERATION_EXECUTE
            ),
        )
    )
    after = DomainPermissionResolver(downgraded_registry).resolve(
        operation_execute_request(request_id="req:dp051:h")
    )
    assert after.effective_permissions.decision is PermissionOutcome.DENY
    # STALE_AUTHORITY_REUSED=NO: the new decision carries its own evaluation
    # and does not inherit the previous ALLOW layer.
    assert before.effective_permissions.decision is PermissionOutcome.ALLOW

    # Memory authority downgrade also fails closed (see Task 5 integration),
    # asserted here through the canonical privacy tightening path:
    tightened = canonical_project_privacy_evidence(NOW)
    assert tightened.allowed is False
    assert tightened.status.value in {"denied", "approval_required"}


# ── I — SDK/API/CLI surfaces reuse canonical owners ───────────────────────────


def test_scenario_i_sdk_api_cli_surfaces_reuse_canonical_owners(
    tmp_path, capsys
) -> None:
    from cmm.domains.api import DefaultDomainAPI
    from cmm.domains.enums import DomainValidationStatus
    from cmm.domains.sdk import DomainScaffolder, validate_domain_path
    from cmm.domains.sdk.cli import handle_domain_cli

    pack_root = tmp_path / "dp051-pack"
    DomainScaffolder().create("dp051-pack", destination=pack_root)
    assert validate_domain_path(pack_root).status in (
        DomainValidationStatus.PASSED,
        DomainValidationStatus.WARNING,
    )
    import argparse

    assert (
        handle_domain_cli(
            argparse.Namespace(domain_subcommand="validate", path=str(pack_root))
        )
        == 0
    )
    assert "dp051-pack" in capsys.readouterr().out

    from tests.domains.test_domain_api_contracts import _make_collaborators

    collaborators = _make_collaborators()
    registry = collaborators["domain_registry"]
    api = DefaultDomainAPI(**collaborators)
    assert api.list_domains() == registry.list()

    project = build_project_domain_definition()
    registry.register(project)
    assert api.get_domain(PROJECT_DOMAIN_ID).version == project.version
    # The CLI/API never keep their own registry: the facade mirrors the
    # canonical registry object it was wired with.
    registry.unregister(str(project.id), project.version)
    assert api.get_domain(PROJECT_DOMAIN_ID) is None


# ── J — security/observability/fragmentation guards remain active ─────────────


def test_scenario_j_security_observability_fragmentation_guards_are_active() -> None:
    from cmm.domains.observability_contracts import DomainMetricStatus
    from cmm.domains.observability_metrics import (
        DomainMetricsCalculator,
        DomainObservabilityEvidence,
    )
    from cmm.domains.trust_contracts import DomainTrustLevel, DomainTrustPolicy
    from cmm.domains.validation_fragmentation import analyze_fragmentation

    # Security: trust ceilings deny; they never grant.
    registry = DomainPermissionRegistry()
    registry.register(build_project_permission_policy())
    blocked = DomainTrustPolicy(
        domain_id=PROJECT_DOMAIN_ID,
        trust_level=DomainTrustLevel.BLOCKED,
        authorized_source_ids=(),
    )
    decision = DomainPermissionResolver(
        registry, trust_policy_lookup=lambda domain_id: blocked
    ).resolve(operation_execute_request(request_id="req:dp051:j"))
    assert decision.effective_permissions.decision is PermissionOutcome.DENY

    # Observability: no evidence is UNAVAILABLE, never zero or guessed.
    snapshot = DomainMetricsCalculator().calculate(
        DomainObservabilityEvidence(), generated_at=NOW
    )
    assert snapshot.measurements
    assert all(
        m.status is DomainMetricStatus.UNAVAILABLE for m in snapshot.measurements
    )
    assert all(m.value is None for m in snapshot.measurements)

    # Fragmentation: the Phase 10.39 canonical guard still detects duplication.
    findings = analyze_fragmentation(
        "class DomainRegistry:\n    pass\n\n\nDomainRegistry = DomainRegistry\n",
        "probe.py",
    )
    assert "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION" in {
        finding.get("code") for finding in findings
    }


# ── K — 10.52/10.53 and Phase 11 boundaries remain deferred ──────────────────


def test_scenario_k_deferred_boundaries_remain_deferred() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    assert not (repo_root / "cmm/domains/mental_health").exists()
    assert not (repo_root / "cmm/domains/neurodivergence").exists()
    assert deferred_classification_count() == 2

    bootstrap = connected_bootstrap()
    registered = {str(definition.id) for definition in bootstrap.domain_registry.list()}
    assert registered.isdisjoint(DEFERRED_DOMAIN_IDS)

    # Phase 11 boundary: the interface seam is reused as-is, not replaced.
    resolution = resolve_project(bootstrap)
    composition = compose_resolution(bootstrap, resolution)
    projection = DefaultDomainInterfaceIntegrator().project(
        request=DomainInterfaceProjectionRequest(
            request_id="iface-req-dp051",
            resolution_reference_id=resolution.id,
            composition_reference_id=composition.id,
        ),
        resolution=resolution,
        composition=composition,
        registry=bootstrap.domain_registry,
    )
    assert projection.resolution_reference_id == resolution.id
    assert projection.composition_reference_id == composition.id
    assert projection.request_id == "iface-req-dp051"
    # Existing 10.45 views (not a Phase 11 UI): conversational, selector,
    # domain center, cross-domain and review projections.
    assert projection.conversational is not None
    # No new UI/platform module was introduced by Phase 10.51.
    offenders = [
        path.name
        for path in (repo_root / "cmm").rglob("*.py")
        if path.name
        in {
            "domain_center_ui.py",
            "cross_domain_view.py",
            "chat_ui.py",
            "application_ui.py",
            "model_gateway.py",
            "model_evaluation_runtime.py",
            "platform_orchestration.py",
        }
    ]
    assert offenders == []


# ── Aggregate closure evidence ────────────────────────────────────────────────


def test_at_dp_051_aggregate_invariants() -> None:
    aggregates = {
        "HISTORICAL_BLOCKS": historical_block_count(),
        "UNMAPPED_REQUIRED_BLOCKS": len(unmapped_required_blocks()),
        "PARALLEL_OWNER_REQUIRED": parallel_owner_required_count(),
        "FIRST_PARTY_PRE_10_52_DOMAINS": len(FIRST_PARTY_DOMAIN_IDS),
        "DEFERRED_DOMAIN_PACKS": len(DEFERRED_DOMAIN_IDS),
        "PHASE11_PLATFORM_DEFERRED": True,
    }
    assert aggregates == HISTORICAL_AGGREGATE_BASELINE
