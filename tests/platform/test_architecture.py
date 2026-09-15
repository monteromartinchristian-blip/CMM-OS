"""Phase 11.1 – Task 9 architecture gates for the platform integration core.

The canonical binding builders must accept already-constructed subsystem
objects and must never reconstruct a canonical subsystem.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_PACKAGE = REPO_ROOT / "cmm" / "platform"
CANONICAL_MODULE = PLATFORM_PACKAGE / "canonical.py"

# ── Canonical imports used only to build real subsystem objects ---------------

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
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
from cmm.cognitive.registries import (
    KnowledgeExtractorRegistry,
    ResourceAdapterRegistry,
)
from cmm.cognitive.service import ResourceExtractionService
from cmm.domains.registry import DomainRegistry
from cmm.execution.executor_registry import ExecutorRegistry
from cmm.platform.canonical import (
    agent_runtime_integration_binding,
    cognitive_adapter_registry_binding,
    cognitive_extractor_registry_binding,
    cognitive_service_binding,
    domain_registry_binding,
    execution_registry_binding,
    provider_registry_binding,
    validation_application_binding,
    workflow_registry_binding,
)
from cmm.validation.interfaces.application import ValidationApplicationService
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry
from kernel.llm.provider_state import SCHEMA_VERSION as PROVIDER_STATE_SCHEMA_VERSION

# ── Canonical subsystem ownership gates ──────────────────────────────────────

#: Classes owned by canonical subsystems.  ``cmm.platform`` must never define a
#: competing owner, and ``canonical.py`` must never construct one.
FORBIDDEN_OWNER_CLASSES = (
    "ProviderRegistry",
    "DomainRegistry",
    "AgentRuntimeIntegrationService",
    "ValidationApplicationService",
    "ResourceExtractionService",
    "ResourceAdapterRegistry",
    "KnowledgeExtractorRegistry",
    "InMemoryWorkflowRegistry",
    "ExecutorRegistry",
    "KnowledgeStore",
    "KnowledgeGraph",
    "AgentRuntime",
    "WorkflowEngine",
    "Planner",
    "ValidationEngine",
    "EventBus",
    "ToolRegistry",
)

ORCHESTRATION_SYMBOLS = (
    "Orchestrator",
    "IntentResolver",
    "ContextResolver",
    "DomainRouter",
    "AgentRouter",
    "OrchestrationRequest",
    "OrchestrationResult",
)


# ── Test-local canonical graph (official construction patterns) ──────────────


def _real_agent_runtime_integration_service() -> AgentRuntimeIntegrationService:
    """Build the real Agent Runtime integration service from canonical parts."""

    goal_manager = GoalManager()
    return AgentRuntimeIntegrationService(
        store=InMemoryAgentRuntimeIntegrationStore(),
        goal_manager=goal_manager,
        registry_service=AgentRegistryService(
            registry=AgentRegistry(), factory_registry=AgentFactoryRegistry()
        ),
        runtime_loop=AgentRuntimeLoop(goal_repository=goal_manager.repository),
        security_service=AgentSecurityService(),
        budget_service=ActionBudgetService(),
        execution_adapter=AgentExecutionAdapter(
            execution_delegate=lambda operation: {"ok": True}
        ),
    )


def _real_cognitive_registries() -> tuple[
    ResourceAdapterRegistry, KnowledgeExtractorRegistry
]:
    return ResourceAdapterRegistry(), KnowledgeExtractorRegistry()


# ── Task 9: identity preservation ────────────────────────────────────────────


def test_provider_binding_reuses_exact_canonical_registry_instance() -> None:
    providers = ProviderRegistry()

    binding = provider_registry_binding(providers)

    assert binding.implementation is providers
    assert binding.descriptor.service_id == "provider.registry"
    assert binding.descriptor.authority == "provider-registry"


def test_provider_binding_uses_canonical_phase_11_34_schema_version() -> None:
    binding = provider_registry_binding(ProviderRegistry())

    assert binding.descriptor.contract.schema_version == PROVIDER_STATE_SCHEMA_VERSION
    assert binding.descriptor.contract.owner == "kernel.llm"


def test_domain_registry_binding_preserves_identity() -> None:
    registry = DomainRegistry()

    binding = domain_registry_binding(registry)

    assert binding.implementation is registry
    assert binding.descriptor.service_id == "domain.registry"


def test_workflow_registry_binding_preserves_identity() -> None:
    registry = InMemoryWorkflowRegistry()

    binding = workflow_registry_binding(registry)

    assert binding.implementation is registry
    assert binding.descriptor.service_id == "workflow.registry"


def test_execution_registry_binding_preserves_identity() -> None:
    registry = ExecutorRegistry()

    binding = execution_registry_binding(registry)

    assert binding.implementation is registry
    assert binding.descriptor.service_id == "execution.registry"


def test_validation_binding_preserves_identity(tmp_path: Path) -> None:
    service = ValidationApplicationService(project_root=tmp_path)

    binding = validation_application_binding(service)

    assert binding.implementation is service
    assert binding.descriptor.service_id == "validation.application"
    assert binding.descriptor.contract.owner == "cmm.validation"


def test_cognitive_service_binding_preserves_identity() -> None:
    adapters, extractors = _real_cognitive_registries()
    service = ResourceExtractionService(adapters, extractors)

    binding = cognitive_service_binding(service)

    assert binding.implementation is service
    assert binding.descriptor.service_id == "cognitive.service"


def test_cognitive_service_declares_its_real_construction_dependencies() -> None:
    adapters, extractors = _real_cognitive_registries()
    service = ResourceExtractionService(adapters, extractors)

    binding = cognitive_service_binding(service)

    assert tuple(
        dependency.service_id for dependency in binding.descriptor.dependencies
    ) == ("cognitive.adapter_registry", "cognitive.extractor_registry")


def test_cognitive_registry_bindings_preserve_identity() -> None:
    adapters, extractors = _real_cognitive_registries()

    adapter_binding = cognitive_adapter_registry_binding(adapters)
    extractor_binding = cognitive_extractor_registry_binding(extractors)

    assert adapter_binding.implementation is adapters
    assert adapter_binding.descriptor.service_id == "cognitive.adapter_registry"
    assert extractor_binding.implementation is extractors
    assert extractor_binding.descriptor.service_id == "cognitive.extractor_registry"


def test_agent_runtime_integration_binding_preserves_identity() -> None:
    service = _real_agent_runtime_integration_service()

    binding = agent_runtime_integration_binding(service)

    assert binding.implementation is service
    assert binding.descriptor.service_id == "agent.runtime.integration"


def test_builders_do_not_declare_fabricated_dependencies() -> None:
    """Only real composition requirements may appear as dependencies."""

    bindings = (
        provider_registry_binding(ProviderRegistry()),
        domain_registry_binding(DomainRegistry()),
        workflow_registry_binding(InMemoryWorkflowRegistry()),
        execution_registry_binding(ExecutorRegistry()),
        agent_runtime_integration_binding(_real_agent_runtime_integration_service()),
    )

    for binding in bindings:
        assert binding.descriptor.dependencies == (), (
            f"{binding.descriptor.service_id} declares a fabricated dependency"
        )


def test_implementation_id_is_derived_from_the_canonical_type() -> None:
    binding = domain_registry_binding(DomainRegistry())

    assert binding.descriptor.implementation_id == (
        "cmm.domains.registry.DomainRegistry"
    )


# ── Task 9: no hidden subsystem reconstruction ───────────────────────────────


def _called_names(tree: ast.AST) -> set[str]:
    """Collect every called name, ignoring comments and string literals."""

    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name):
            called.add(callee.id)
        elif isinstance(callee, ast.Attribute):
            called.add(callee.attr)
    return called


def test_canonical_builders_do_not_reconstruct_subsystems() -> None:
    tree = ast.parse(CANONICAL_MODULE.read_text())

    forbidden = sorted(_called_names(tree) & set(FORBIDDEN_OWNER_CLASSES))

    assert not forbidden, (
        f"cmm/platform/canonical.py must not construct canonical owners: {forbidden}"
    )


def test_canonical_module_is_a_pure_binding_layer() -> None:
    """The builder module must contain no module-level mutable state."""

    tree = ast.parse(CANONICAL_MODULE.read_text())

    def is_constant_declaration(node: ast.Assign) -> bool:
        for target in node.targets:
            if not isinstance(target, ast.Name):
                return False
            # Upper-case constants and dunder declarations such as __all__
            # are declarations, not mutable state.
            if target.id.startswith("__") or target.id.isupper():
                continue
            return False
        return True

    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign) and not is_constant_declaration(node)
    ]

    assert not assignments, "canonical.py must not hold module-level mutable state"
