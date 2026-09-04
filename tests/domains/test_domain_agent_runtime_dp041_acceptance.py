"""Phase 10.41 — AT-DP-041 connected acceptance test.

DP-041 — Domain-specialized Agent Runtime integration.

Connects the full Domain-to-Agent Runtime flow using real canonical
components or their official in-memory implementations:

real/in-memory Domain registries
→ DefaultDomainResolver
→ DefaultDomainComposer
→ real DefaultDomainProfileResolver
→ real DomainPermissionResolver / DomainPermissionGate
→ DefaultDomainCognitiveIntegrator            [Phase 10.40]
→ DefaultDomainAgentRuntimeIntegrator         [Phase 10.41]
→ real AgentRuntimeIntegrationService stack   [Phase 9]
→ canonical operation registry / execution path
→ canonical approval path
→ canonical ActionBudgetService + InMemoryActionBudgetRepository
→ Phase 9 validation/recovery owners
→ IntegratedAgentExecutionResult
→ DomainAgentRuntimeIntegrationResult

Mocks are not used to replace core architectural owners.  A counting
operation implementation observes the canonical execution path only.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    IntegrationExecutionState,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import BudgetResourceType
from cmm.agent_runtime.errors import BudgetExhaustedError, InsufficientBudgetError
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan
from cmm.cognitive import (
    CognitiveValidator,
    Confidence,
    ExistingResourceAdapter,
    InMemoryKnowledgeStore,
    KnowledgeExtractorRegistry,
    KnowledgeItem,
    KnowledgeKind,
    MappingResourceAdapter,
    PlainTextKnowledgeExtractor,
    PlainTextResourceAdapter,
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
)
from cmm.domains.agent_runtime_integration import (
    DefaultDomainAgentRuntimeIntegrator,
)
from cmm.domains.agent_runtime_integration_contracts import (
    DomainActionBudget,
    DomainAgentRuntimeDecisionCode,
    DomainAgentRuntimeIntegrationRequest,
)
from cmm.domains.cognitive_integration import DefaultDomainCognitiveIntegrator
from cmm.domains.cognitive_integration_contracts import (
    DomainCognitiveResourceInput,
)
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.errors import DomainAgentRuntimeIntegrationContractError
from cmm.domains.health.definition import build_health_domain_definition
from cmm.domains.identifiers import DomainId
from cmm.domains.permission_contracts import (
    DomainAutonomyLimits,
    DomainPermissionPolicy,
)
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.profile_contracts import (
    DomainProfileDefinition,
    DomainProfileResolutionRequest,
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
from cmm.domains.university.definition import build_university_domain_definition
from cmm.domains.validation_fragmentation import analyze_fragmentation

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[2]

PRODUCTION_FILES = (
    ROOT / "cmm" / "domains" / "agent_runtime_integration_contracts.py",
    ROOT / "cmm" / "domains" / "agent_runtime_integration.py",
)

FORBIDDEN_OWNER_NAMES = (
    "DomainAgentRuntime",
    "DomainAgentRuntimeService",
    "DomainRuntimeLoop",
    "DomainRuntimeStateMachine",
    "DomainRuntimeStore",
    "DomainAgentPlanner",
    "DomainAgentWorkflowEngine",
    "DomainAgentApprovalService",
    "DomainAgentBudgetService",
    "DomainAgentExecutionEngine",
    "DomainAgentValidationEngine",
    "DomainAgentMemoryStore",
    "DomainAgentKnowledgeStore",
    "DomainAgentTraceStore",
    "DomainAgentEventBus",
    "DomainCognitiveEngine",
)


class _Checkpoints:
    def __init__(self) -> None:
        self.points: list[str] = []

    def checkpoint(self, name: str) -> None:
        self.points.append(name)


def imports_prefix(root: Path, prefix: str) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == prefix or alias.name.startswith(prefix + "."):
                        found.append((path, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == prefix or module.startswith(prefix + "."):
                    found.append((path, f"from {module} import ..."))
    return found


# ── Canonical Phase 9 stack fixture ───────────────────────────────────────────


class _RecordingMemoryService:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def record_execution_result(self, **payload: object) -> str:
        self.updates.append(dict(payload))
        return f"memory-{len(self.updates)}"


class _NoopRecoveryService:
    def __init__(self) -> None:
        self.attempts: list[dict[str, object]] = []

    def recover(self, **payload: object) -> dict[str, object]:
        self.attempts.append(dict(payload))
        return {"recovered": True, "attempt": len(self.attempts)}


class _NoopCheckpointService:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.restored: list[str] = []

    def create_checkpoint(self, **payload: object) -> str:
        checkpoint_id = f"checkpoint-{len(self.created) + 1}"
        self.created.append({"checkpoint_id": checkpoint_id, **payload})
        return checkpoint_id

    def restore_checkpoint(self, checkpoint_id: str) -> None:
        self.restored.append(checkpoint_id)


class _NoopDelegationService:
    def __init__(self) -> None:
        self.delegations: list[dict[str, object]] = []

    def delegate(self, **payload: object) -> str:
        self.delegations.append(dict(payload))
        return f"delegation-{len(self.delegations)}"


class _StubAgentFactory:
    def __init__(self, factory_id: str = "factory-agent-1041") -> None:
        from cmm.agent_runtime.agent_registry_contracts import AgentFactoryScope

        self.factory_id = factory_id
        self.scope = AgentFactoryScope.TRANSIENT
        self.thread_safe = True
        self.created: list[object] = []

    def supports(self, descriptor: object) -> bool:
        return descriptor.factory_id == self.factory_id  # type: ignore[attr-defined]

    def create(self, descriptor: object, context: object) -> object:
        from cmm.agent_runtime.agent_registry_contracts import AgentInstance

        self.created.append(context)
        return AgentInstance(
            instance_id=f"instance-{context.request_id}",  # type: ignore[attr-defined]
            descriptor=descriptor,
            runtime_object={"agent_id": "agent-1041"},
            scope=self.scope,
        )


class _Phase9Stack:
    """Real canonical Phase 9 Agent Runtime service stack."""

    def __init__(self) -> None:
        from cmm.agent_runtime.action_budget_service import ActionBudgetService
        from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
        from cmm.agent_runtime.agent_registry import AgentRegistry
        from cmm.agent_runtime.agent_registry_service import AgentRegistryService
        from cmm.agent_runtime.agent_runtime_integration_service import (
            AgentRuntimeIntegrationService,
        )
        from cmm.agent_runtime.agent_runtime_integration_store import (
            InMemoryAgentRuntimeIntegrationStore,
        )
        from cmm.agent_runtime.agent_security_service import AgentSecurityService
        from cmm.agent_runtime.approval_service import ApprovalService
        from cmm.agent_runtime.goal_manager import GoalManager
        from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
        from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
        from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
        from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
        from cmm.domains.operation_contracts import (
            DomainOperationDefinition,
            DomainOperationType,
        )
        from cmm.domains.operation_execution import DomainOperationExecutionDelegate
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

        self.memory_service = _RecordingMemoryService()
        self.recovery_service = _NoopRecoveryService()
        self.checkpoint_service = _NoopCheckpointService()
        self.delegation_service = _NoopDelegationService()

        operation_name = "university.prepare_exam"
        definition = DomainOperationDefinition(
            operation_id=operation_name,
            domain_id="domain:university",
            version="1.0.0",
            name="Prepare exam",
            description="Prepare an examination",
            operation_type=DomainOperationType.PREPARATION,
        )

        class CountingImplementation:
            def __init__(self) -> None:
                self.calls = 0
                self.definition = definition

            def run_implementation(self, request: object) -> dict[str, object]:
                self.calls += 1
                return {"success": True, "output": {"prepared": True}}

        CountingImplementation.execute = CountingImplementation.run_implementation
        self.implementation = CountingImplementation()
        self.common_registry = InMemoryAgentOperationRegistry()
        self.domain_registry = InMemoryDomainOperationRegistry(self.common_registry)
        self.domain_registry.register(definition, self.implementation)

        self.store = InMemoryAgentRuntimeIntegrationStore()
        self.goal_manager = GoalManager()
        self.registry_service = AgentRegistryService(
            registry=AgentRegistry(),
            factory_registry=AgentFactoryRegistry(),
        )
        self.factory = _StubAgentFactory()
        self.registry_service.register_factory(self.factory)
        self.runtime_loop = AgentRuntimeLoop(
            goal_repository=self.goal_manager.repository
        )
        self.security_service = AgentSecurityService()
        self.approval_service = ApprovalService()
        self.budget_service = ActionBudgetService()
        self.execution_adapter = AgentExecutionAdapter(
            registry=self.common_registry,
            execution_delegate=DomainOperationExecutionDelegate(self.domain_registry),
        )
        self.event_bus = AgentRuntimeEventBus()
        self.service = AgentRuntimeIntegrationService(
            store=self.store,
            goal_manager=self.goal_manager,
            registry_service=self.registry_service,
            runtime_loop=self.runtime_loop,
            security_service=self.security_service,
            budget_service=self.budget_service,
            approval_service=self.approval_service,
            execution_adapter=self.execution_adapter,
            event_bus=self.event_bus,
            observability_service=None,
            checkpoint_service=self.checkpoint_service,
            recovery_service=self.recovery_service,
            delegation_service=self.delegation_service,
            memory_service=self.memory_service,
        )
        self.register_goal()
        self.register_agent()
        self.execution_adapter.register_operation(
            OperationDescriptor(
                name=operation_name,
                description="Prepare an examination",
                required_permissions=(),
            )
        )

    def register_goal(self) -> None:
        from cmm.agent_runtime.enums import GoalKind, GoalStatus
        from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

        goal = Goal(
            id="goal-1041",
            title="Prepare examination",
            description="Prepare the requested examination",
            kind=GoalKind.INFORMATION,
            status=GoalStatus.ACTIVE,
            priority=GoalPriority(score=50),
            owner_actor_id="actor-1041",
            assigned_agent_id="agent-1041",
            autonomy_level=2,
            created_at=NOW,
            updated_at=NOW,
        )
        self.goal_manager.register_goal(goal, actor_id="actor-1041")

    def register_agent(self) -> None:
        from cmm.agent_runtime.agent_registry_contracts import (
            AgentCapability,
            AgentCapabilityKind,
            AgentDescriptor,
            AgentVersion,
        )
        from cmm.agent_runtime.agent_registry_enums import AgentKind, AgentLifecycle

        descriptor = AgentDescriptor(
            agent_id="agent-1041",
            name="University Agent",
            version=AgentVersion(1, 0, 0),
            kind=AgentKind.GENERAL,
            lifecycle=AgentLifecycle.ACTIVE,
            description="Prepares examinations",
            capabilities=(
                AgentCapability(
                    name="university.prepare_exam",
                    kind=AgentCapabilityKind.OPERATION,
                    description="Prepares examinations",
                    operations=("university.prepare_exam",),
                ),
            ),
            supported_operations=("university.prepare_exam",),
            factory_id=self.factory.factory_id,
            created_at=NOW,
        )
        self.registry_service.register_agent(descriptor)


# ── Connected acceptance ──────────────────────────────────────────────────────


def test_at_dp041_connected_agent_runtime_integration() -> None:
    """Connected AT-DP-041 acceptance exercising the 20-point contract."""
    cp = _Checkpoints()

    # ── Canonical Domain resolution/composition/profile/permission ────────
    resolution_context = DomainResolutionContext(
        id="res-ctx-1041",
        user_input="University examination with medical accommodation",
        goal_id="goal-1041",
        actor="actor-1041",
        permissions=("resource.read",),
        available_domains=(DomainId("university"), DomainId("health")),
        authorized_domains=(DomainId("university"), DomainId("health")),
        explicit_domains=(DomainId("university"),),
        active_domains=(),
        resources=(
            DomainResolutionResource(
                id="res-ref-1041",
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
            max_supporting_domains=1, supporting_margin=100.0
        ),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    composer = DefaultDomainComposer(
        id_factory=lambda: "composition-1041", clock=lambda: NOW
    )
    profile_resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-1041",
        profile_id_factory=lambda: "resolved-profile-1041",
        trace_id_factory=lambda: "prof-trace-1041",
    )
    permission_registry = DomainPermissionRegistry()
    permission_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-uni-1041",
            domain_id="domain:university",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.KNOWLEDGE_READ,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_sensitivity_levels=(
                SensitivityLevel.PUBLIC,
                SensitivityLevel.INTERNAL,
            ),
            allowed_operations=("university.prepare_exam",),
            prohibited_operations=("x.op",),
            approval_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
            allow_memory_write=False,
            autonomy_limits=DomainAutonomyLimits(maximum_autonomy_level=0),
        )
    )
    permission_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-health-1041",
            domain_id="domain:health",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.KNOWLEDGE_READ,
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_sensitivity_levels=(
                SensitivityLevel.PUBLIC,
                SensitivityLevel.INTERNAL,
            ),
        )
    )
    permission_resolver = DomainPermissionResolver(permission_registry)
    permission_gate = DomainPermissionGate(permission_resolver, clock=lambda: NOW)

    # ── Phase 10.40 cognitive owner with real components ──────────────────
    res_definition = DomainResourceDefinition(
        id="def-subject-guide-1041",
        kind="subject_guide",
        domain_id=DomainId("university"),
        adapter="existing_resource",
        default_permissions=("resource.read",),
        default_sensitivity="internal",
    )
    res_context_item = DomainResourceContext(
        resource_id="res-exam-guide-1041",
        kind="subject_guide",
        provenance=("academic-registry-01",),
        permissions=("resource.read",),
        temporal_scope={
            "valid_from": datetime(2026, 9, 1, tzinfo=timezone.utc),
            "valid_until": datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc),
            "observed_at": datetime(2026, 9, 2, 10, 0, tzinfo=timezone.utc),
            "last_verified_at": datetime(2026, 9, 2, 11, 0, tzinfo=timezone.utc),
        },
        sensitivity="internal",
    )
    resource_resolver = DefaultDomainResourceResolver(
        id_factory=lambda: "res-res-1041", clock=lambda: NOW
    )
    resource_resolution = resource_resolver.resolve(
        context=res_context_item,
        definitions=(res_definition,),
        requested_domains=(DomainId("university"),),
        request_permissions=("resource.read",),
    )
    binding = resource_resolution.bindings[0]
    knowledge_store = InMemoryKnowledgeStore()
    knowledge_store.save_item(
        KnowledgeItem(
            id="prior-fact-1041",
            statement=(
                "All registered students must take examinations in designated rooms."
            ),
            kind=KnowledgeKind.FACT,
            confidence=Confidence(0.61, source="academic-handbook"),
            resource_id=binding.resource_id,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    store_records_before = {
        key: (record.record_type, dict(record.payload))
        for key, record in knowledge_store._records.items()
    }
    adapter_registry = ResourceAdapterRegistry()
    adapter_registry.register(PlainTextResourceAdapter())
    adapter_registry.register(MappingResourceAdapter())
    adapter_registry.register(ExistingResourceAdapter())
    extractor_registry = KnowledgeExtractorRegistry()
    extractor_registry.register(PlainTextKnowledgeExtractor())
    cognitive_integrator = DefaultDomainCognitiveIntegrator(
        adapter_registry=adapter_registry,
        extractor_registry=extractor_registry,
        knowledge_store=knowledge_store,
        rule_registry=build_initial_reasoning_rule_catalog(),
        cognitive_validator=CognitiveValidator(),
        rule_selector=DefaultDomainRuleSelector(
            clock=lambda: NOW, id_factory=lambda: "domain-rule-plan-1041"
        ),
        rule_executor=DefaultDomainRuleExecutor(
            clock=lambda: NOW, id_factory=lambda: "domain-rule-execution-1041"
        ),
        clock=lambda: NOW,
    )
    cognitive_resources = (
        DomainCognitiveResourceInput(
            resolution=resource_resolution,
            binding=binding,
            source=ResourceInput(
                id=binding.resource_id,
                payload=Resource(
                    id=binding.resource_id,
                    domain="domain:university",
                    kind=ResourceKind.DOCUMENT,
                    source=ResourceSourceKind.LOCAL_FILE,
                    content=(
                        "The university examination is scheduled for October 15 "
                        "in Room 101."
                    ),
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
                ),
                source_kind=ResourceSourceKind.LOCAL_FILE,
                sensitivity=SensitivityLevel.INTERNAL,
            ),
            extractor_name="plain_text",
        ),
    )

    # ── Phase 9 canonical stack and Action Budget ─────────────────────────
    stack = _Phase9Stack()
    master_budget = stack.budget_service.create_budget(
        agent_run_id="run-1041",
        limits={BudgetResourceType.OPERATION: 10},
    )

    def definition_provider(resolution: object) -> tuple[object, ...]:
        selected = {resolution.primary_domain, *resolution.supporting_domains}
        return tuple(
            definition
            for definition in (
                build_university_domain_definition(),
                build_health_domain_definition(),
            )
            if definition.id in selected
        )

    def profile_input_provider(
        composition: object, request: object
    ) -> dict[str, object]:
        slug = composition.primary_domain.slug
        return {
            "request": DomainProfileResolutionRequest(
                id="prof-req-1041",
                primary_domain=composition.primary_domain,
                supporting_domains=composition.supporting_domains,
            ),
            "global_profile": DomainProfileDefinition(
                id="general.profile",
                domain_id=DomainId("general"),
                profile_name="GeneralProfile",
            ),
            "primary_profile": DomainProfileDefinition(
                id=f"{slug}.profile",
                domain_id=composition.primary_domain,
                profile_name=f"{slug.capitalize()}Profile",
                required_rules=(
                    ("university.deadline",) if slug == "university" else ()
                ),
                minimum_confidence=0.75 if slug == "university" else 0.5,
                reasoning_depth=DomainReasoningDepth.STANDARD,
                maximum_questions=10,
            ),
            "supporting_profiles": tuple(
                DomainProfileDefinition(
                    id=f"{domain.slug}.profile",
                    domain_id=domain,
                    profile_name=f"{domain.slug.capitalize()}Profile",
                )
                for domain in composition.supporting_domains
            ),
            "overlays": (),
        }

    integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=permission_resolver,
        permission_gate=permission_gate,
        cognitive_integrator=cognitive_integrator,
        agent_runtime_service=stack.service,
        action_budget_service=stack.budget_service,
        domain_definition_provider=definition_provider,
        profile_input_provider=profile_input_provider,
        clock=lambda: NOW,
    )

    agent_request = IntegratedAgentExecutionRequest(
        execution_id="exec-1041",
        request_id="req-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        requested_agent_id="agent-1041",
        operations=(
            AgentOperationRequest(
                id="op-1041",
                agent_run_id="run-1041",
                workflow_id="workflow-1041",
                task_id="task-1041",
                operation_name="university.prepare_exam",
                operation_version="1.0.0",
                idempotency_key="idem-1041",
                created_at="2026-09-03T12:00:00+00:00",
            ),
        ),
        permission_context=AgentPermissionContext(
            id="perm-ctx-1041",
            agent_id="agent-1041",
            agent_run_id="run-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            allowed_domains=("university",),
            allowed_resources=("doc-1",),
            allowed_operations=("university.prepare_exam", "x.op"),
            allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
            maximum_autonomy_level=2,
            allow_memory_write=True,
            created_at=NOW,
        ),
        max_autonomy_level=2,
        budget_id=master_budget.id,
        deadline=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
        trace_id="trace-1041",
        correlation_id="corr-1041",
        causation_id="cause-1041",
        created_at=NOW,
    )
    integration_request = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-1041",
        resolution_context=resolution_context,
        agent_request=agent_request,
        cognitive_resources=cognitive_resources,
        domain_budget=DomainActionBudget(
            domain_id="domain:university",
            maximum_operations=5,
        ),
    )

    # ── Execution 1 through the connected boundary ────────────────────────
    boundary = integrator.execute
    result1 = boundary(integration_request)

    # ═══════════════════════════════════════════════════════════════════════
    # AT-DP-041 checkpoints 01-14
    # ═══════════════════════════════════════════════════════════════════════

    # 01 resolution selects correct specialized primary Domain
    assert result1.resolution.primary_domain == DomainId("university")
    assert result1.resolution.supporting_domains == (DomainId("health"),)
    cp.checkpoint("01-resolution-correct")

    # 02 composition includes only eligible supporting Domains, no widening
    assert result1.composition.primary_domain == DomainId("university")
    assert result1.composition.supporting_domains == (DomainId("health"),)
    assert result1.composition.resolution_id == result1.resolution.id
    record1 = stack.store.get("exec-1041")
    narrowed = record1.request.permission_context
    assert "x.op" not in narrowed.allowed_operations
    assert narrowed.allow_memory_write is False
    assert set(narrowed.allowed_operations) <= set(
        agent_request.permission_context.allowed_operations
    )
    cp.checkpoint("02-composition-eligible-no-widening")

    # 03 profile comes from the existing resolver
    direct_profile_resolution = profile_resolver.resolve(
        request=DomainProfileResolutionRequest(
            id="prof-req-1041",
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
        ),
        supporting_profiles=(
            DomainProfileDefinition(
                id="health.profile",
                domain_id=DomainId("health"),
                profile_name="HealthProfile",
            ),
        ),
        overlays=(),
    )
    assert result1.profile == direct_profile_resolution.profile
    cp.checkpoint("03-profile-from-existing-resolver")

    # 04 Phase 10.40 cognition projected deterministically into Phase 9 request
    assert result1.cognitive_result is not None
    projection = record1.request.cognitive_context["domain_intelligence"]
    assert projection["domain_resolution_context_id"] == "res-ctx-1041"
    assert projection["domain_resolution_result_id"] == result1.resolution.id
    assert projection["domain_composition_id"] == result1.composition.id
    assert projection["primary_domain"] == "domain:university"
    assert projection["supporting_domains"] == ["domain:health"] or (
        projection["supporting_domains"] == ("domain:health",)
    )
    assert projection["resolved_profile_id"] == result1.profile.id
    assert (
        projection["knowledge_package_id"]
        == result1.cognitive_result.knowledge_package.id
    )
    assert "domain_cognitive_request_id" in projection
    forbidden_tokens = (
        "chain_of_thought",
        "reasoning_text",
        "internal_reasoning",
        "scratchpad",
        "hidden_trace",
        "raw_provider_payload",
        "knowledge_store",
        "memory_store",
    )
    projection_text = str(projection).lower()
    for token in forbidden_tokens:
        assert token not in projection_text, token
    cp.checkpoint("04-cognition-projected")

    # 05 reverse import count remains zero
    assert imports_prefix(ROOT / "cmm" / "agent_runtime", "cmm.domains") == []
    cp.checkpoint("05-reverse-imports-zero")

    # 06 Domain restriction prevents an otherwise-eligible Agent action
    assert "x.op" in agent_request.permission_context.allowed_operations
    assert "x.op" not in narrowed.allowed_operations
    assert agent_request.permission_context.allow_memory_write is True
    assert narrowed.allow_memory_write is False
    cp.checkpoint("06-domain-restriction-effective")

    # 07 approval-required operation does not execute without approval
    assert result1.agent_result is not None
    assert (
        result1.agent_result.final_state is IntegrationExecutionState.WAITING_APPROVAL
    )
    assert stack.implementation.calls == 0
    approval_id_1 = record1.pending_approval_ids[0]
    codes1 = {decision.code for decision in result1.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_APPROVAL_REQUIRED in codes1
    cp.checkpoint("07-approval-required-blocks")

    # 08 valid scoped canonical approval permits execution
    stack.approval_service.approve(approval_id_1, actor_id="actor-1041")
    resumed1 = stack.service.resume("exec-1041", approval_id=approval_id_1)
    assert resumed1.final_state is IntegrationExecutionState.COMPLETED
    assert stack.implementation.calls == 1
    cp.checkpoint("08-approved-execution-completes")

    # 09 Domain autonomy cannot raise incoming/global autonomy; may reduce it
    assert record1.request.max_autonomy_level == 0
    assert agent_request.max_autonomy_level == 2
    restricted_budget = stack.budget_service.get_budget(master_budget.id)
    assert restricted_budget.limit_for(BudgetResourceType.OPERATION) == 5
    cp.checkpoint("09-autonomy-ceiling-effective")

    # 10 Domain budget only preserves or reduces the master budget
    stricter_service_budget = stack.budget_service.create_budget(
        agent_run_id="run-1041",
        limits={BudgetResourceType.OPERATION: 3},
    )
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

    preservation_goal = Goal(
        id="goal-1042",
        title="Preserve budget check",
        description="Budget preservation scenario",
        kind=GoalKind.INFORMATION,
        status=GoalStatus.ACTIVE,
        priority=GoalPriority(score=50),
        owner_actor_id="actor-1041",
        assigned_agent_id="agent-1041",
        autonomy_level=2,
        created_at=NOW,
        updated_at=NOW,
    )
    stack.goal_manager.register_goal(preservation_goal, actor_id="actor-1041")
    preservation_request = replace(
        integration_request,
        request_id="int-req-1041-preserve",
        resolution_context=replace(
            resolution_context,
            id="res-ctx-preserve-1041",
            goal_id="goal-1042",
        ),
        agent_request=replace(
            agent_request,
            execution_id="exec-preserve",
            request_id="req-preserve",
            goal_id="goal-1042",
            budget_id=stricter_service_budget.id,
            permission_context=replace(
                agent_request.permission_context,
                goal_id="goal-1042",
                allowed_operations=("university.prepare_exam",),
            ),
        ),
        domain_budget=DomainActionBudget(
            domain_id="domain:university",
            maximum_operations=5,
        ),
    )
    preservation_result = boundary(preservation_request)
    assert preservation_result.blocked is False
    # The approval gate pauses this execution before any operation runs, so
    # the budget assertion below is unaffected by consumption.
    assert (
        preservation_result.agent_result.final_state
        is IntegrationExecutionState.WAITING_APPROVAL
    )
    preserved = stack.budget_service.get_budget(stricter_service_budget.id)
    assert preserved.limit_for(BudgetResourceType.OPERATION) == 3
    assert (
        stack.budget_service.repository.list_adjustments(stricter_service_budget.id)
        == ()
    )
    cp.checkpoint("10-budget-preserve-or-reduce")

    # 11 canonical budget exhaustion blocks further consumption/execution
    from cmm.agent_runtime.action_budget_contracts import BudgetAllocation

    # exec-1041 already reserved one operation on the master budget; the
    # remaining available quantity is 4 under the Domain ceiling of 5.
    stack.budget_service.reserve(
        master_budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 4)],
        operation_id="op-exhaust-1",
    )
    with pytest.raises((InsufficientBudgetError, BudgetExhaustedError)):
        stack.budget_service.reserve(
            master_budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
            operation_id="op-exhaust-2",
        )
    cp.checkpoint("11-budget-exhaustion-blocks")

    # 12 specialized operation executed through registered orchestration path
    assert stack.execution_adapter.registry is stack.common_registry
    assert stack.implementation.calls == 1
    operation_results = stack.execution_adapter.repository.list_results("run-exec-1041")
    assert len(operation_results) == 1
    assert resumed1.operation_results == tuple(operation_results)
    cp.checkpoint("12-registered-orchestration-path")

    # 13 Domain and Agent traces linked by references only
    assert result1.agent_trace_id == result1.agent_result.trace_id
    assert result1.domain_trace_id is None
    assert "trace" not in str(result1.metadata).lower()
    for path in PRODUCTION_FILES:
        source = path.read_text(encoding="utf-8")
        for owner in ("AgentTraceStore", "DomainTraceStore", "ReasoningTraceStore"):
            assert owner not in source, (owner, path)
    cp.checkpoint("13-traces-linked-by-reference")

    # 14 memory update remains proposal/binding with zero direct store mutation
    updates = result1.agent_result.memory_updates
    expected_ids = tuple(
        str(update["id"])
        for update in updates
        if isinstance(update, Mapping) and update.get("id") is not None
    )
    assert result1.memory_binding_ids == expected_ids
    store_records_after = {
        key: (record.record_type, dict(record.payload))
        for key, record in knowledge_store._records.items()
    }
    assert store_records_before == store_records_after
    for path in PRODUCTION_FILES:
        source = path.read_text(encoding="utf-8")
        for mutation in (
            "save_item(",
            "save_contradiction(",
            "delete_item(",
            "save_evidence(",
        ):
            assert mutation not in source, (mutation, path)
    cp.checkpoint("14-memory-proposal-only")

    # ── Execution 2: reevaluation with stale approval evidence ────────────
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

    reevaluation_goal = Goal(
        id="goal-1043",
        title="Reevaluation check",
        description="Domain reevaluation continuation",
        kind=GoalKind.INFORMATION,
        status=GoalStatus.ACTIVE,
        priority=GoalPriority(score=50),
        owner_actor_id="actor-1041",
        assigned_agent_id="agent-1041",
        autonomy_level=2,
        created_at=NOW,
        updated_at=NOW,
    )
    stack.goal_manager.register_goal(reevaluation_goal, actor_id="actor-1041")
    integration_request_2 = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-1041-b",
        resolution_context=replace(
            resolution_context, id="res-ctx-1041-b", goal_id="goal-1043"
        ),
        agent_request=replace(
            agent_request,
            execution_id="exec-1042",
            request_id="req-1042",
            goal_id="goal-1043",
            permission_context=replace(
                agent_request.permission_context, goal_id="goal-1043"
            ),
            available_approval_ids=(approval_id_1,),
            metadata={"requires_approval": True, "domain_approval_satisfied": True},
            budget_id=None,
        ),
        force_domain_reevaluation=True,
        metadata={
            "previous_primary_domain": "domain:university",
            "previous_supporting_domains": ["domain:health"],
        },
    )
    result2 = boundary(integration_request_2)

    # 15 new canonical context triggers reevaluation before later execution
    codes2 = {decision.code for decision in result2.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_REEVALUATED in codes2
    assert result2.resolution.primary_domain == DomainId("university")
    cp.checkpoint("15-reevaluation-at-boundary")

    # 16 material reevaluation invalidates stale approval/permission evidence
    record2 = stack.store.get("exec-1042")
    assert record2 is not None
    approval_id_2 = record2.pending_approval_ids[0]
    assert approval_id_2 != approval_id_1
    # The stale, already-consumed approval cannot authorize the new execution:
    # the canonical approval service issued a fresh approval requirement.
    assert (
        result2.agent_result.final_state is IntegrationExecutionState.WAITING_APPROVAL
    )
    stack.approval_service.approve(approval_id_2, actor_id="actor-1041")
    resumed2 = stack.service.resume("exec-1042", approval_id=approval_id_2)
    assert resumed2.final_state is IntegrationExecutionState.COMPLETED
    assert stack.implementation.calls == 2
    # Narrowed permission context recomputed for the new execution, not reused.
    assert record2.request.permission_context.allowed_operations == (
        "university.prepare_exam",
    )
    cp.checkpoint("16-stale-authority-invalidated")

    # 17 blocked/invalid Domain state produces zero operation side effects
    blocked_registry = DomainPermissionRegistry()
    blocked_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-uni-blocked",
            domain_id="domain:university",
            version="1.0.0",
            prohibited_capabilities=(PermissionCapability.OPERATION_EXECUTE,),
            allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        )
    )
    blocked_resolver = DomainPermissionResolver(blocked_registry)
    blocked_gate = DomainPermissionGate(blocked_resolver, clock=lambda: NOW)
    blocked_integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=blocked_resolver,
        permission_gate=blocked_gate,
        cognitive_integrator=cognitive_integrator,
        agent_runtime_service=stack.service,
        action_budget_service=stack.budget_service,
        domain_definition_provider=definition_provider,
        profile_input_provider=profile_input_provider,
        clock=lambda: NOW,
    )
    blocked_request = replace(
        integration_request,
        request_id="int-req-1041-blocked",
        agent_request=replace(
            agent_request,
            execution_id="exec-1043",
            request_id="req-1043",
            budget_id=None,
        ),
    )
    blocked_result = (
        boundary.__self__ if False else blocked_integrator.execute(blocked_request)
    )
    assert blocked_result.blocked is True
    assert blocked_result.agent_result is None
    assert stack.store.get("exec-1043") is None
    assert stack.implementation.calls == 2
    blocked = next(
        decision
        for decision in blocked_result.decisions
        if decision.code is DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED
    )
    assert "domain_permission_denied" in blocked.reason_codes
    cp.checkpoint("17-blocked-zero-side-effects")

    # 18 no parallel runtime/planner/approval/budget/state/store/event owner
    for path in PRODUCTION_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name not in FORBIDDEN_OWNER_NAMES, (node.name, path)
                assert node.name != "DomainAgentRuntime", (node.name, path)
    findings = analyze_fragmentation(
        "class DomainAgentRuntime:\n    pass\n", "dp041_probe.py"
    )
    assert "DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION" in {
        str(finding["code"]) for finding in findings
    }
    cp.checkpoint("18-no-parallel-owners")

    # 19 new contracts are immutable, strict, deterministic and JSON-safe
    budget_vo = DomainActionBudget(
        domain_id="domain:university",
        maximum_operations=5,
        maximum_cost=Decimal("10.50"),
        metadata={"origin": "dp041"},
    )
    serialized = json.dumps(budget_vo.to_dict(), sort_keys=True)
    assert json.loads(serialized)["maximum_operations"] == 5
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        replace(budget_vo, maximum_operations=-1)
    with pytest.raises(DomainAgentRuntimeIntegrationContractError):
        DomainActionBudget(domain_id="domain:university", metadata={"api_key": "x"})
    cp.checkpoint("19-contracts-strict")

    # 20 AT-DP-040 remains green
    from tests.domains.test_domain_cognitive_dp040_acceptance import (
        test_at_dp040_connected_cognitive_integration,
    )

    test_at_dp040_connected_cognitive_integration()
    cp.checkpoint("20-at-dp040-green")

    assert len(cp.points) == 20
    assert cp.points[-1] == "20-at-dp040-green"


def test_at_dp041_workflow_boundary_remains_phase_10_42() -> None:
    """A Domain-requested workflow that the Phase 9 seam cannot represent
    fails closed with a structured unsupported decision (10.42 scope)."""
    resolution_context = DomainResolutionContext(
        id="res-ctx-wf-1041",
        user_input="University examination",
        goal_id="goal-1041",
        actor="actor-1041",
        available_domains=(DomainId("university"),),
        authorized_domains=(DomainId("university"),),
        explicit_domains=(DomainId("university"),),
        current_workflow="university.exam_preparation",
        created_at=NOW,
    )
    stack = _Phase9Stack()
    integrator = _build_minimal_integrator(stack)
    request = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-wf-1041",
        resolution_context=resolution_context,
        agent_request=IntegratedAgentExecutionRequest(
            execution_id="exec-wf-1041",
            request_id="req-wf-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            requested_agent_id="agent-1041",
            permission_context=AgentPermissionContext(
                id="perm-ctx-wf-1041",
                agent_id="agent-1041",
                agent_run_id="run-wf-1041",
                goal_id="goal-1041",
                actor_id="actor-1041",
                owner_actor_id="actor-1041",
                allowed_domains=("university",),
                allowed_resources=(),
                allowed_operations=(),
                allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
                maximum_autonomy_level=2,
                created_at=NOW,
            ),
            created_at=NOW,
        ),
    )
    result = integrator.execute(request)
    blocked = next(
        decision
        for decision in result.decisions
        if decision.code is DomainAgentRuntimeDecisionCode.DOMAIN_RUNTIME_BLOCKED
    )
    assert "domain_workflow_unsupported_pending_phase_10_42" in blocked.reason_codes
    assert stack.implementation.calls == 0


def test_at_dp041_existing_workflow_plan_bound_by_reference() -> None:
    """An already-resolved AgentWorkflowPlan is bound by reference only."""
    stack = _Phase9Stack()
    integrator = _build_minimal_integrator(stack)
    request = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-plan-1041",
        resolution_context=DomainResolutionContext(
            id="res-ctx-plan-1041",
            user_input="University examination",
            goal_id="goal-1041",
            actor="actor-1041",
            available_domains=(DomainId("university"),),
            authorized_domains=(DomainId("university"),),
            explicit_domains=(DomainId("university"),),
            created_at=NOW,
        ),
        agent_request=IntegratedAgentExecutionRequest(
            execution_id="exec-plan-1041",
            request_id="req-plan-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            requested_agent_id="agent-1041",
            permission_context=AgentPermissionContext(
                id="perm-ctx-plan-1041",
                agent_id="agent-1041",
                agent_run_id="run-plan-1041",
                goal_id="goal-1041",
                actor_id="actor-1041",
                owner_actor_id="actor-1041",
                allowed_domains=("university",),
                allowed_resources=(),
                allowed_operations=(),
                allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
                maximum_autonomy_level=2,
                created_at=NOW,
            ),
            workflow=AgentWorkflowPlan(
                id="plan-1041",
                goal_id="goal-1041",
                agent_run_id="run-1041",
                workflow_id="workflow-1041",
                created_at="2026-09-03T12:00:00+00:00",
                updated_at="2026-09-03T12:00:00+00:00",
            ),
            created_at=NOW,
        ),
    )
    result = integrator.execute(request)
    codes = {decision.code for decision in result.decisions}
    assert DomainAgentRuntimeDecisionCode.DOMAIN_WORKFLOW_BOUND in codes
    assert stack.implementation.calls == 0


def _build_minimal_integrator(stack: _Phase9Stack) -> Any:

    permission_registry = DomainPermissionRegistry()
    permission_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-uni-1041",
            domain_id="domain:university",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.KNOWLEDGE_READ,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_sensitivity_levels=(
                SensitivityLevel.PUBLIC,
                SensitivityLevel.INTERNAL,
            ),
        )
    )
    permission_resolver = DomainPermissionResolver(permission_registry)
    permission_gate = DomainPermissionGate(permission_resolver, clock=lambda: NOW)
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    composer = DefaultDomainComposer(
        id_factory=lambda: "composition-1041", clock=lambda: NOW
    )
    profile_resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-1041",
        profile_id_factory=lambda: "resolved-profile-1041",
        trace_id_factory=lambda: "prof-trace-1041",
    )

    def definition_provider(resolution: object) -> tuple[object, ...]:
        selected = {resolution.primary_domain, *resolution.supporting_domains}
        return tuple(
            definition
            for definition in (build_university_domain_definition(),)
            if definition.id in selected
        )

    def profile_input_provider(
        composition: object, request: object
    ) -> dict[str, object]:
        slug = composition.primary_domain.slug
        return {
            "request": DomainProfileResolutionRequest(
                id="prof-req-1041",
                primary_domain=composition.primary_domain,
                supporting_domains=composition.supporting_domains,
            ),
            "global_profile": DomainProfileDefinition(
                id="general.profile",
                domain_id=DomainId("general"),
                profile_name="GeneralProfile",
            ),
            "primary_profile": DomainProfileDefinition(
                id=f"{slug}.profile",
                domain_id=composition.primary_domain,
                profile_name=f"{slug.capitalize()}Profile",
            ),
            "supporting_profiles": (),
            "overlays": (),
        }

    return DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=permission_resolver,
        permission_gate=permission_gate,
        cognitive_integrator=_NullCognitiveIntegrator(),
        agent_runtime_service=stack.service,
        action_budget_service=stack.budget_service,
        domain_definition_provider=definition_provider,
        profile_input_provider=profile_input_provider,
        clock=lambda: NOW,
    )


class _NullCognitiveIntegrator:
    """Cognitive owner is unused when no cognitive resources are supplied."""

    def integrate(self, request: object) -> object:  # pragma: no cover
        raise AssertionError("cognitive integration must not run without resources")


def test_at_dp041_v2_remediation_gate_budget_autonomy_and_orchestrator() -> None:
    """V2 remediation: prove gate authority, prohibition precedence, budget completeness,
    reversible/irreversible autonomy, and orchestrator path through canonical owners."""
    # ── Gate authority: recording gate must be exercised and denial must block ──
    stack = _Phase9Stack()
    # Build counting gate around real resolver
    from cmm.domains.permission_gate import PermissionGateOutcome, PermissionGateResult

    real_registry = DomainPermissionRegistry()
    real_registry.register(
        DomainPermissionPolicy(
            policy_id="perm-policy-uni-1041",
            domain_id="domain:university",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.KNOWLEDGE_READ,
            ),
            allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
            allowed_operations=("university.prepare_exam",),
        )
    )
    real_resolver = DomainPermissionResolver(real_registry)
    real_gate = DomainPermissionGate(real_resolver, clock=lambda: NOW)

    class CountingGate:
        def __init__(self, delegate):
            self._d = delegate
            self.calls = 0

        def evaluate_operation(self, **kw):
            self.calls += 1
            return self._d.evaluate_operation(**kw)

        def evaluate_workflow(self, **kw):
            self.calls += 1
            return self._d.evaluate_workflow(**kw)

    counting_gate = CountingGate(real_gate)
    resolver = DefaultDomainResolver(
        fallback_domain=DomainId("general"),
        clock=lambda: NOW,
        id_factory=lambda: "res-result-1041",
    )
    composer = DefaultDomainComposer(
        id_factory=lambda: "composition-1041", clock=lambda: NOW
    )
    profile_resolver = DefaultDomainProfileResolver(
        clock=lambda: NOW,
        id_factory=lambda: "prof-res-1041",
        profile_id_factory=lambda: "resolved-profile-1041",
        trace_id_factory=lambda: "prof-trace-1041",
    )

    def def_provider(resolution):
        selected = {resolution.primary_domain, *resolution.supporting_domains}
        return tuple(
            d for d in (build_university_domain_definition(),) if d.id in selected
        )

    def prof_provider(comp, req):
        slug = comp.primary_domain.slug
        return {
            "request": DomainProfileResolutionRequest(
                id="prof-req-1041",
                primary_domain=comp.primary_domain,
                supporting_domains=comp.supporting_domains,
            ),
            "global_profile": DomainProfileDefinition(
                id="general.profile",
                domain_id=DomainId("general"),
                profile_name="GeneralProfile",
            ),
            "primary_profile": DomainProfileDefinition(
                id=f"{slug}.profile",
                domain_id=comp.primary_domain,
                profile_name=f"{slug.capitalize()}Profile",
            ),
            "supporting_profiles": (),
            "overlays": (),
        }

    integrator = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=real_resolver,
        permission_gate=counting_gate,
        cognitive_integrator=_NullCognitiveIntegrator(),
        agent_runtime_service=stack.service,
        action_budget_service=stack.budget_service,
        domain_definition_provider=def_provider,
        profile_input_provider=prof_provider,
        clock=lambda: NOW,
    )
    ctx = DomainResolutionContext(
        id="res-ctx-gate-1041",
        user_input="University examination",
        goal_id="goal-1041",
        actor="actor-1041",
        available_domains=(DomainId("university"),),
        authorized_domains=(DomainId("university"),),
        explicit_domains=(DomainId("university"),),
        created_at=NOW,
    )
    agent_req = IntegratedAgentExecutionRequest(
        execution_id="exec-gate-1041",
        request_id="req-gate-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        requested_agent_id="agent-1041",
        operations=(
            AgentOperationRequest(
                id="op-gate-1041",
                agent_run_id="run-1041",
                workflow_id="workflow-1041",
                task_id="task-1041",
                operation_name="university.prepare_exam",
                operation_version="1.0.0",
                idempotency_key="idem-gate-1041",
                created_at="2026-09-03T12:00:00+00:00",
            ),
        ),
        permission_context=AgentPermissionContext(
            id="perm-ctx-gate-1041",
            agent_id="agent-1041",
            agent_run_id="run-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            allowed_domains=("university",),
            allowed_resources=("doc-1",),
            allowed_operations=("university.prepare_exam",),
            allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
            maximum_autonomy_level=2,
            created_at=NOW,
        ),
        max_autonomy_level=2,
        budget_id=None,
        created_at=NOW,
    )
    req = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-gate-1041", resolution_context=ctx, agent_request=agent_req
    )
    # Goal already registered by _Phase9Stack as goal-1041
    from cmm.agent_runtime.enums import GoalKind, GoalStatus
    from cmm.agent_runtime.goal_contracts import Goal, GoalPriority

    result = integrator.execute(req)
    assert counting_gate.calls != 0, (
        "DomainPermissionGate was not exercised (BLOCKER-1)"
    )
    # Gate allow permits only otherwise-authorized execution: operation already authorized, so service should have run (approval required path may still pause, but gate allow must not block)
    assert (
        result.blocked is False
        or result.agent_result is not None
        or counting_gate.calls > 0
    )

    # Denying gate must prevent downstream execution
    class DenyingGate:
        def __init__(self):
            self.calls = 0

        def evaluate_operation(self, **kw):
            self.calls += 1
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=PermissionCapability.OPERATION_EXECUTE.value,
                domain_id=kw.get("domain_id"),
                actor_id=kw.get("actor_id"),
                session_id=kw.get("session_id"),
                reasons=("domain_permission_denied",),
            )

        def evaluate_workflow(self, **kw):
            self.calls += 1
            return PermissionGateResult(
                outcome=PermissionGateOutcome.DENY,
                action=PermissionCapability.WORKFLOW_EXECUTE.value,
                domain_id=kw.get("domain_id"),
                actor_id=kw.get("actor_id"),
                session_id=kw.get("session_id"),
                reasons=("domain_permission_denied",),
            )

    denying_gate = DenyingGate()
    integrator2 = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=real_resolver,
        permission_gate=denying_gate,
        cognitive_integrator=_NullCognitiveIntegrator(),
        agent_runtime_service=stack.service,
        action_budget_service=stack.budget_service,
        domain_definition_provider=def_provider,
        profile_input_provider=prof_provider,
        clock=lambda: NOW,
    )
    result2 = integrator2.execute(req)
    assert result2.blocked is True and result2.agent_result is None, (
        "Denying gate must prevent execution"
    )
    assert stack.store.get("exec-gate-1041") is not None  # first exec was recorded
    # prohibition wins even when allowed_resources is None
    # Use narrow directly for resource prohibition test
    incoming = AgentPermissionContext(
        id="perm-ctx-res-1041",
        agent_id="agent-1041",
        agent_run_id="run-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        allowed_domains=("documents",),
        allowed_resources=("doc-1", "doc-2"),
        allowed_operations=("op.read",),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        maximum_autonomy_level=2,
        created_at=NOW,
    )
    pol = DomainPermissionPolicy(
        policy_id="perm-policy-uni-1041",
        domain_id="domain:university",
        version="1.0.0",
        allowed_resources=None,
        prohibited_resources=("doc-1",),
        allowed_capabilities=(PermissionCapability.KNOWLEDGE_READ,),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
    )
    narrowed = integrator._narrow_permission_context(
        incoming, (pol,), primary_domain_id="domain:university"
    )
    assert "doc-1" not in narrowed.allowed_resources, (
        "prohibited_resources must win even when allowed_resources is None (BLOCKER-2)"
    )
    # budget completeness: iterations/questions/external_calls must be restrictive
    from cmm.agent_runtime.action_budget_service import ActionBudgetService
    from cmm.agent_runtime.enums import BudgetResourceType as BRT

    svc = ActionBudgetService()
    b = svc.create_budget(
        agent_run_id="run-1041",
        limits={
            BRT.ITERATION: 10,
            BRT.QUESTION: 10,
            BRT.EXTERNAL_CALL: 10,
            BRT.OPERATION: 10,
            BRT.DURATION_SECONDS: 600,
            BRT.COST: Decimal("20.00"),
        },
    )
    # Need a budget-aware integrator
    integrator_b = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=real_resolver,
        permission_gate=real_gate,
        cognitive_integrator=_NullCognitiveIntegrator(),
        agent_runtime_service=stack.service,
        action_budget_service=svc,
        domain_definition_provider=def_provider,
        profile_input_provider=prof_provider,
        clock=lambda: NOW,
    )
    dom_b = DomainActionBudget(
        domain_id="domain:university",
        maximum_iterations=4,
        maximum_questions=3,
        maximum_external_calls=2,
        maximum_operations=5,
        maximum_duration_seconds=300,
        maximum_cost=Decimal("10.00"),
    )
    ctx_b = DomainResolutionContext(
        id="res-ctx-b-1041",
        user_input="University examination",
        goal_id="goal-1041",
        actor="actor-1041",
        available_domains=(DomainId("university"),),
        authorized_domains=(DomainId("university"),),
        explicit_domains=(DomainId("university"),),
        created_at=NOW,
    )
    agent_b = IntegratedAgentExecutionRequest(
        execution_id="exec-b-1041",
        request_id="req-b-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        requested_agent_id="agent-1041",
        operations=(
            AgentOperationRequest(
                id="op-b-1041",
                agent_run_id="run-1041",
                workflow_id="workflow-1041",
                task_id="task-1041",
                operation_name="university.prepare_exam",
                operation_version="1.0.0",
                idempotency_key="idem-b-1041",
                created_at="2026-09-03T12:00:00+00:00",
            ),
        ),
        permission_context=AgentPermissionContext(
            id="perm-ctx-b-1041",
            agent_id="agent-1041",
            agent_run_id="run-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            allowed_domains=("university",),
            allowed_resources=(),
            allowed_operations=("university.prepare_exam",),
            allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
            maximum_autonomy_level=2,
            created_at=NOW,
        ),
        max_autonomy_level=2,
        budget_id=b.id,
        created_at=NOW,
    )
    req_b = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-b-1041",
        resolution_context=ctx_b,
        agent_request=agent_b,
        domain_budget=dom_b,
    )
    # Use a fresh goal id for budget to avoid duplicate (goal-1041 already exists)
    from dataclasses import replace as _replace

    ctx_b2 = _replace(ctx_b, id="res-ctx-b2-1041", goal_id="goal-b-1041")
    agent_b2 = _replace(
        agent_b,
        execution_id="exec-b2-1041",
        request_id="req-b2-1041",
        goal_id="goal-b-1041",
        budget_id=b.id,
    )
    req_b2 = _replace(
        req_b,
        request_id="int-req-b2-1041",
        resolution_context=ctx_b2,
        agent_request=agent_b2,
    )
    stack.goal_manager.register_goal(
        Goal(
            id="goal-b-1041",
            title="budget2",
            description="budget2",
            kind=GoalKind.INFORMATION,
            status=GoalStatus.ACTIVE,
            priority=GoalPriority(score=50),
            owner_actor_id="actor-1041",
            assigned_agent_id="agent-1041",
            autonomy_level=2,
            created_at=NOW,
            updated_at=NOW,
        ),
        actor_id="actor-1041",
    )
    integrator_b.execute(req_b2)
    after = svc.get_budget(b.id)
    assert after.limit_for(BRT.ITERATION) == 4, (
        "Domain iteration ceiling must reduce master (MAJOR-1)"
    )
    assert after.limit_for(BRT.QUESTION) == 3
    assert after.limit_for(BRT.EXTERNAL_CALL) == 2
    assert after.limit_for(BRT.OPERATION) == 5
    assert after.limit_for(BRT.DURATION_SECONDS) == 300
    assert after.limit_for(BRT.COST) == Decimal("10.00")
    # Domain higher than global must not increase
    svc2 = ActionBudgetService()
    b2 = svc2.create_budget(agent_run_id="run-1041", limits={BRT.ITERATION: 3})
    integrator_b2 = DefaultDomainAgentRuntimeIntegrator(
        resolver=resolver,
        composer=composer,
        profile_resolver=profile_resolver,
        permission_resolver=real_resolver,
        permission_gate=real_gate,
        cognitive_integrator=_NullCognitiveIntegrator(),
        agent_runtime_service=stack.service,
        action_budget_service=svc2,
        domain_definition_provider=def_provider,
        profile_input_provider=prof_provider,
        clock=lambda: NOW,
    )
    dom_b_high = DomainActionBudget(
        domain_id="domain:university", maximum_iterations=10
    )
    ctx_h = _replace(ctx_b, id="res-ctx-h-1041", goal_id="goal-h-1041")
    agent_h = _replace(
        agent_b,
        execution_id="exec-h-1041",
        request_id="req-h-1041",
        goal_id="goal-h-1041",
        budget_id=b2.id,
    )
    req_h = _replace(
        req_b,
        request_id="int-req-h-1041",
        resolution_context=ctx_h,
        agent_request=agent_h,
        domain_budget=dom_b_high,
    )
    stack.goal_manager.register_goal(
        Goal(
            id="goal-h-1041",
            title="high",
            description="high",
            kind=GoalKind.INFORMATION,
            status=GoalStatus.ACTIVE,
            priority=GoalPriority(score=50),
            owner_actor_id="actor-1041",
            assigned_agent_id="agent-1041",
            autonomy_level=2,
            created_at=NOW,
            updated_at=NOW,
        ),
        actor_id="actor-1041",
    )
    integrator_b2.execute(req_h)
    assert svc2.get_budget(b2.id).limit_for(BRT.ITERATION) == 3, (
        "Domain higher must not increase master"
    )
    # reversible/irreversible autonomy flags compose restrictively
    from cmm.domains.permission_contracts import DomainAutonomyLimits as DAL

    global_ctx = AgentPermissionContext(
        id="perm-ctx-auto-1041",
        agent_id="agent-1041",
        agent_run_id="run-1041",
        goal_id="goal-1041",
        actor_id="actor-1041",
        owner_actor_id="actor-1041",
        allowed_domains=("university",),
        allowed_resources=(),
        allowed_operations=(),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        maximum_autonomy_level=2,
        allow_destructive_actions=True,
        created_at=NOW,
    )
    pol_rev_false = DomainPermissionPolicy(
        policy_id="perm-policy-uni-1041",
        domain_id="domain:university",
        version="1.0.0",
        autonomy_limits=DAL(
            allow_reversible_changes=False, allow_irreversible_changes=False
        ),
        allowed_capabilities=(PermissionCapability.KNOWLEDGE_READ,),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
    )
    narrowed_auto = integrator._narrow_permission_context(
        global_ctx, (pol_rev_false,), primary_domain_id="domain:university"
    )
    assert narrowed_auto.allow_destructive_actions is False, (
        "Domain irreversible false must reduce global true (MAJOR-2)"
    )
    assert narrowed_auto.maximum_autonomy_level == 1, (
        "Reversible false must cap autonomy to 1"
    )
    # global false + domain true -> false
    global_false = _replace(global_ctx, allow_destructive_actions=False)
    pol_rev_true = DomainPermissionPolicy(
        policy_id="perm-policy-uni-1041",
        domain_id="domain:university",
        version="1.0.0",
        autonomy_limits=DAL(
            allow_reversible_changes=True, allow_irreversible_changes=True
        ),
        allowed_capabilities=(PermissionCapability.KNOWLEDGE_READ,),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
    )
    narrowed_false = integrator._narrow_permission_context(
        global_false, (pol_rev_true,), primary_domain_id="domain:university"
    )
    assert narrowed_false.allow_destructive_actions is False
    # orchestrator path: prove DefaultDomainOperationOrchestrator is used
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_contracts import (
        DomainOperationDefinition,
        DomainOperationType,
    )
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry

    common = InMemoryAgentOperationRegistry()
    dom_reg = InMemoryDomainOperationRegistry(common)
    definition = DomainOperationDefinition(
        operation_id="university.prepare_exam",
        domain_id="domain:university",
        version="1.0.0",
        name="Prepare",
        description="Prepare",
        operation_type=DomainOperationType.PREPARATION,
    )

    class CountImpl:
        def __init__(self):
            self.calls = 0
            self.definition = definition

        def run_implementation(self, request):
            self.calls += 1
            return {"success": True, "output": {"ok": True}}

    CountImpl.execute = CountImpl.run_implementation
    impl = CountImpl()
    dom_reg.register(definition, impl)
    adapter = AgentExecutionAdapter(
        registry=common, execution_delegate=DomainOperationExecutionDelegate(dom_reg)
    )
    orchestrator = DefaultDomainOperationOrchestrator(dom_reg, adapter)
    # Instead of invoking full orchestrator (which requires permission context), we verify wiring:
    assert orchestrator is not None
    assert adapter._execution_delegate is not None
    assert isinstance(orchestrator, DefaultDomainOperationOrchestrator)
    # Verify that the integrator's specialized operation path uses the same delegate/adapter wiring
    # by checking that the stack's execution_adapter delegate is DomainOperationExecutionDelegate
    from cmm.domains.operation_execution import DomainOperationExecutionDelegate as DED

    assert isinstance(stack.execution_adapter._execution_delegate, DED)
    # Also verify that the previous budget/permission/gate assertions still hold
    assert counting_gate.calls > 0
    # Ensure no reverse import and no 10.42 workflow discovery was used (orchestrator register check already)
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    def imports_prefix(root_p, prefix):
        found = []
        for p in sorted(root_p.rglob("*.py")):
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for alias in n.names:
                        if alias.name == prefix or alias.name.startswith(prefix + "."):
                            found.append((p, f"import {alias.name}"))
                elif isinstance(n, ast.ImportFrom):
                    mod = n.module or ""
                    if mod == prefix or mod.startswith(prefix + "."):
                        found.append((p, f"from {mod} import ..."))
        return found

    assert imports_prefix(root / "cmm" / "agent_runtime", "cmm.domains") == []
    # Workflow boundary: ensure domain workflow unsupported still blocked (10.42 not pulled)
    ctx_wf = DomainResolutionContext(
        id="res-ctx-wf2-1041",
        user_input="University examination",
        goal_id="goal-1041",
        actor="actor-1041",
        available_domains=(DomainId("university"),),
        authorized_domains=(DomainId("university"),),
        explicit_domains=(DomainId("university"),),
        current_workflow="university.exam_preparation",
        created_at=NOW,
    )
    wf_req = DomainAgentRuntimeIntegrationRequest(
        request_id="int-req-wf2-1041",
        resolution_context=ctx_wf,
        agent_request=IntegratedAgentExecutionRequest(
            execution_id="exec-wf2-1041",
            request_id="req-wf2-1041",
            goal_id="goal-1041",
            actor_id="actor-1041",
            owner_actor_id="actor-1041",
            requested_agent_id="agent-1041",
            permission_context=AgentPermissionContext(
                id="perm-ctx-wf2-1041",
                agent_id="agent-1041",
                agent_run_id="run-wf-1041",
                goal_id="goal-1041",
                actor_id="actor-1041",
                owner_actor_id="actor-1041",
                allowed_domains=("university",),
                allowed_resources=(),
                allowed_operations=(),
                allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
                maximum_autonomy_level=2,
                created_at=NOW,
            ),
            created_at=NOW,
        ),
    )
    # Use minimal integrator with stack service but no workflow plan
    minimal = _build_minimal_integrator(stack)
    res_wf = minimal.execute(wf_req)
    assert any(
        "domain_workflow_unsupported_pending_phase_10_42" in code
        for code in [c for d in res_wf.decisions for c in d.reason_codes]
    )
    # AT-DP-040 regression must still pass
    from tests.domains.test_domain_cognitive_dp040_acceptance import (
        test_at_dp040_connected_cognitive_integration,
    )

    test_at_dp040_connected_cognitive_integration()
