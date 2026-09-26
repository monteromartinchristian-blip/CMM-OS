"""Phase 11.1 – Architecture gates for the platform integration core.

Two responsibilities are covered here:

* Task 9 gates: the canonical binding builders must accept already-constructed
  subsystem objects and must never reconstruct a canonical subsystem.
* Task 10 gates: dependency direction, scope (no Phase 11.2 orchestration),
  duplicate-owner prohibition and import-time side-effect freedom.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_PACKAGE = REPO_ROOT / "cmm" / "platform"
CANONICAL_MODULE = PLATFORM_PACKAGE / "canonical.py"

#: Packages the design places explicitly *above* ``cmm.platform``: the Phase
#: 11.2 orchestration layer and the Phase 11.3 application backend.  They are
#: not canonical subsystems, they consume the Phase 11.1 composition core
#: (readiness container plus composition module contracts), and the exact
#: allowlist below keeps that exemption bounded.
#: Phase 11.5 (DP-105) sanctions ``cmm.conversation`` as the third sanctioned
#: consumer: it binds ``conversation.service`` through the same Phase 11.1
#: composition contracts and owns no platform authority of its own.
#: Phase 11.50 (DP-150) sanctions ``cmm.client_backend`` as the fourth: it binds
#: ``client.backend`` through the same Phase 11.1 composition contracts, owns no
#: platform authority of its own, and declares no canonical subsystem service as
#: a dependency at all.
#: Phase 11.22 (DP-122) sanctions ``cmm.events`` as the fifth: the platform event
#: system contributes its event-system service bindings through the same Phase
#: 11.1 composition module contracts.  It owns no platform authority, defines no
#: second composition root and no service locator, and it is placed *above*
#: ``cmm.platform`` because composing the canonical event services is exactly
#: what the Phase 11.1 composition core is for.  ``cmm.platform`` itself must
#: never import ``cmm.events``: the dependency direction stays one-way.
PLATFORM_CONSUMER_PACKAGES = (
    "orchestration",
    "application",
    "conversation",
    "client_backend",
    "events",
)

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
from cmm.platform.contracts import (
    ServiceBinding,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.service_registry import IntegrationServiceRegistry
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


# ── Task 10: dependency direction ────────────────────────────────────────────


def _python_files(root: Path, *, exclude: Path | None = None) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*.py")):
        if exclude is not None and exclude in path.parents:
            continue
        files.append(path)
    return files


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def test_canonical_subsystems_do_not_import_the_platform_package() -> None:
    """Dependency direction is one-way: cmm.platform -> canonical subsystems.

    ``cmm.orchestration`` and ``cmm.application`` are excluded because the
    Phase 11.2 and Phase 11.3 designs place them explicitly *above*
    ``cmm.platform`` (``cmm.orchestration -> cmm.platform + canonical
    subsystems``; ``cmm.application`` consumes the Phase 11.1
    ``ApplicationContainer`` and binds its services through the Phase 11.1
    composition contracts), and Phase 11.5 (DP-105) places ``cmm.conversation``
    beside them for the same reason.  They are not canonical subsystems, and
    ``test_only_sanctioned_layers_may_depend_on_the_platform_package`` below
    keeps that exemption exact.
    """

    offenders: list[str] = []

    for root in (REPO_ROOT / "cmm", REPO_ROOT / "kernel"):
        for path in _python_files(root, exclude=PLATFORM_PACKAGE):
            if path.relative_to(REPO_ROOT).parts[1] in PLATFORM_CONSUMER_PACKAGES:
                continue
            for module in _imported_modules(path):
                if module == "cmm.platform" or module.startswith("cmm.platform."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        "canonical subsystem packages must not import cmm.platform: "
        f"{sorted(offenders)}"
    )


def test_only_sanctioned_layers_may_depend_on_the_platform_package() -> None:
    """Only the sanctioned application-level layers may consume the platform core."""

    consumers: set[str] = set()

    for root in (REPO_ROOT / "cmm", REPO_ROOT / "kernel"):
        for path in _python_files(root, exclude=PLATFORM_PACKAGE):
            for module in _imported_modules(path):
                if module == "cmm.platform" or module.startswith("cmm.platform."):
                    package = path.relative_to(REPO_ROOT).parts[1]
                    consumers.add(package)

    assert consumers <= set(PLATFORM_CONSUMER_PACKAGES), (
        "only cmm.orchestration and cmm.application may depend on cmm.platform: "
        f"{sorted(consumers)}"
    )


# ── Task 10: Phase 11.2 scope ────────────────────────────────────────────────


def _platform_module_files() -> list[Path]:
    return sorted(PLATFORM_PACKAGE.glob("*.py"))


def test_platform_package_defines_no_orchestration_symbols() -> None:
    """Phase 11.1 must not pull Phase 11.2 orchestration forward."""

    offenders: list[str] = []

    for path in _platform_module_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in ORCHESTRATION_SYMBOLS
            ):
                offenders.append(f"{path.name}:{node.name}")
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id in ORCHESTRATION_SYMBOLS
                    ):
                        offenders.append(f"{path.name}:{target.id}")

    assert not offenders, f"Phase 11.2 orchestration symbols found: {offenders}"


def test_platform_package_does_not_export_orchestration_symbols() -> None:
    import cmm.platform

    leaked = sorted(set(cmm.platform.__all__) & set(ORCHESTRATION_SYMBOLS))

    assert not leaked, f"cmm.platform exports orchestration symbols: {leaked}"


def test_platform_package_does_not_import_orchestration_modules() -> None:
    """No future orchestration module may be imported to satisfy 11.1."""

    tokens = (
        "orchestrator",
        "orchestration",
        "intent_resolver",
        "context_resolver",
        "domain_router",
        "agent_router",
    )

    offenders: list[str] = []

    for path in _platform_module_files():
        for module in _imported_modules(path):
            last = module.rsplit(".", 1)[-1].lower()
            if any(token in last for token in tokens):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"orchestration modules imported: {sorted(offenders)}"


# ── Task 10: duplicate canonical owners ──────────────────────────────────────


@pytest.mark.parametrize("owner", FORBIDDEN_OWNER_CLASSES)
def test_platform_package_defines_no_duplicate_owner_class(owner: str) -> None:
    """No class may duplicate a canonical subsystem owner.

    ``IntegrationServiceRegistry`` is explicitly allowed: it is a registry of
    platform composition bindings, not a second owner of domain, provider,
    agent, tool or workflow content.
    """

    offenders: list[str] = []

    for path in _platform_module_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith(owner):
                offenders.append(f"{path.name}:{node.name}")

    assert not offenders, f"duplicate canonical owner defined: {offenders}"


def test_integration_service_registry_is_explicitly_allowed() -> None:
    """The one added registry is permitted, and is not a duplicate owner."""

    from cmm.platform import IntegrationServiceRegistry

    assert IntegrationServiceRegistry.__name__ not in FORBIDDEN_OWNER_CLASSES
    assert IntegrationServiceRegistry.__module__.startswith("cmm.platform")
    assert not any(
        IntegrationServiceRegistry.__name__.endswith(owner)
        for owner in FORBIDDEN_OWNER_CLASSES
    )


def test_integration_service_registry_is_the_only_added_registry() -> None:
    import cmm.platform

    added = {name for name in cmm.platform.__all__ if name.endswith("Registry")}

    assert added == {"IntegrationServiceRegistry"}, (
        f"cmm.platform must add exactly one registry, found: {sorted(added)}"
    )


# ── Task 10: import-time side effects ────────────────────────────────────────


def test_importing_platform_registers_nothing_globally() -> None:
    """Importing ``cmm.platform`` must not mutate canonical registries."""

    program = """
import json
import cmm.platform  # noqa: F401
from cmm.domains.registry import DomainRegistry
from cmm.execution.executor_registry import ExecutorRegistry
from cmm.platform.service_registry import IntegrationServiceRegistry
from cmm.workflows.registry import InMemoryWorkflowRegistry
from kernel.llm.provider_registry import ProviderRegistry

print(json.dumps({
    "provider": len(ProviderRegistry().list()),
    "domain": len(DomainRegistry().list()),
    "workflow": len(InMemoryWorkflowRegistry().list_definitions()),
    "execution": len(ExecutorRegistry().all()),
    "integration": len(IntegrationServiceRegistry().list_bindings()),
}))
"""

    import json
    import subprocess

    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        "provider": 0,
        "domain": 0,
        "workflow": 0,
        "execution": 0,
        "integration": 0,
    }


def test_platform_modules_hold_no_module_level_registry_instance() -> None:
    import cmm.platform  # noqa: F401
    from cmm.platform.service_registry import IntegrationServiceRegistry

    canonical_owners = (ProviderRegistry, DomainRegistry, InMemoryWorkflowRegistry)

    def check(module_name: str, module: ModuleType) -> None:
        for attribute, value in vars(module).items():
            assert not isinstance(value, IntegrationServiceRegistry), (
                f"{module_name}.{attribute} is a module-level registry singleton"
            )
            assert not isinstance(value, canonical_owners), (
                f"{module_name}.{attribute} caches a canonical registry instance"
            )

    for module_name, module in list(sys.modules.items()):
        if module_name != "cmm.platform" and not module_name.startswith(
            "cmm.platform."
        ):
            continue
        assert isinstance(module, ModuleType)
        check(module_name, module)


# ── Remediation V1 / MAJOR-01: canonical runtime boundaries ──────────────────


def _real_validation_application(tmp_path: Path) -> ValidationApplicationService:
    return ValidationApplicationService(project_root=tmp_path)


def _real_cognitive_service() -> ResourceExtractionService:
    adapters, extractors = _real_cognitive_registries()
    return ResourceExtractionService(adapters, extractors)


#: ``(service_id, builder, canonical runtime contract, canonical factory)`` for
#: every canonical Phase 11.1 binding whose runtime boundary is safely
#: enforceable with ``isinstance``.
CANONICAL_RUNTIME_BOUNDARY_CASES = (
    (
        "provider.registry",
        provider_registry_binding,
        ProviderRegistry,
        lambda _tmp_path: ProviderRegistry(),
    ),
    (
        "domain.registry",
        domain_registry_binding,
        DomainRegistry,
        lambda _tmp_path: DomainRegistry(),
    ),
    (
        "validation.application",
        validation_application_binding,
        ValidationApplicationService,
        _real_validation_application,
    ),
    (
        "cognitive.adapter_registry",
        cognitive_adapter_registry_binding,
        ResourceAdapterRegistry,
        lambda _tmp_path: ResourceAdapterRegistry(),
    ),
    (
        "cognitive.extractor_registry",
        cognitive_extractor_registry_binding,
        KnowledgeExtractorRegistry,
        lambda _tmp_path: KnowledgeExtractorRegistry(),
    ),
    (
        "cognitive.service",
        cognitive_service_binding,
        ResourceExtractionService,
        lambda _tmp_path: _real_cognitive_service(),
    ),
    (
        "agent.runtime.integration",
        agent_runtime_integration_binding,
        AgentRuntimeIntegrationService,
        lambda _tmp_path: _real_agent_runtime_integration_service(),
    ),
    (
        "workflow.registry",
        workflow_registry_binding,
        InMemoryWorkflowRegistry,
        lambda _tmp_path: InMemoryWorkflowRegistry(),
    ),
    (
        "execution.registry",
        execution_registry_binding,
        ExecutorRegistry,
        lambda _tmp_path: ExecutorRegistry(),
    ),
)


def _case_ids() -> list[str]:
    return [case[0] for case in CANONICAL_RUNTIME_BOUNDARY_CASES]


@pytest.mark.parametrize(
    ("service_id", "builder", "_contract", "_factory"),
    CANONICAL_RUNTIME_BOUNDARY_CASES,
    ids=_case_ids(),
)
def test_canonical_binding_declares_its_enforceable_runtime_contract(
    service_id: str,
    builder: object,
    _contract: type,
    _factory: object,
    tmp_path: Path,
) -> None:
    """A canonical authority must be bound with a checkable implementation boundary."""

    implementation = _factory(tmp_path)  # type: ignore[operator]
    binding = builder(implementation)  # type: ignore[operator]

    assert binding.descriptor.service_id == service_id
    assert binding.implementation is implementation
    assert binding.runtime_contract is _contract
    assert isinstance(binding.implementation, binding.runtime_contract)


@pytest.mark.parametrize(
    ("_service_id", "builder", "_contract", "_factory"),
    CANONICAL_RUNTIME_BOUNDARY_CASES,
    ids=_case_ids(),
)
def test_canonical_binding_rejects_an_unrelated_object(
    _service_id: str,
    builder: object,
    _contract: type,
    _factory: object,
) -> None:
    """Audit V1 MAJOR-01: an arbitrary object must never claim canonical authority."""

    with pytest.raises(TypeError):
        builder(object())  # type: ignore[operator]


@pytest.mark.parametrize(
    ("service_id", "builder", "_contract", "_factory"),
    CANONICAL_RUNTIME_BOUNDARY_CASES,
    ids=_case_ids(),
)
def test_canonical_binding_rejects_an_object_from_another_canonical_authority(
    service_id: str,
    builder: object,
    _contract: type,
    _factory: object,
) -> None:
    """A real canonical object must not be able to claim a different authority."""

    foreign: object = (
        ProviderRegistry() if service_id == "domain.registry" else DomainRegistry()
    )

    with pytest.raises(TypeError):
        builder(foreign)  # type: ignore[operator]


def test_canonical_binding_accepts_the_real_canonical_object_identity() -> None:
    providers = ProviderRegistry()

    binding = provider_registry_binding(providers)

    assert binding.implementation is providers
    assert binding.runtime_contract is ProviderRegistry


def test_registry_keeps_supporting_explicit_non_canonical_replacements(
    tmp_path: Path,
) -> None:
    """Runtime enforcement must not disable the replacement/test-adapter feature."""

    class ValidationPort:
        """Consumer-declared boundary for an alternate implementation."""

    class AlternateValidation(ValidationPort):
        """Compatible adapter-backed implementation; no transport is involved."""

    registry = IntegrationServiceRegistry()
    registry.register(
        validation_application_binding(_real_validation_application(tmp_path))
    )
    original = registry.get("validation.application")
    assert original is not None

    alternate = ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id="validation.application",
            contract=original.descriptor.contract,
            implementation_id="tests.platform.AlternateValidation",
            mode=ServiceMode.ADAPTER,
        ),
        implementation=AlternateValidation(),
        runtime_contract=ValidationPort,
    )

    registry.replace("validation.application", alternate)

    stored = registry.get("validation.application")
    assert stored is not None
    assert isinstance(stored.implementation, AlternateValidation)
    assert stored.runtime_contract is ValidationPort
