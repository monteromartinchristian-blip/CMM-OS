"""Phase 11.2 — executable architecture and scope gates.

These gates turn the Phase 11.2 design prohibitions into executable assertions:

* no duplicate canonical owner;
* no reverse dependency onto ``cmm.orchestration``;
* no Phase 11.3 API/backend leakage;
* no Model Gateway or provider/model routing;
* no import-time mutation;
* no hidden-reasoning public field;
* no runtime service locator;
* no new Event Bus and no new subsystem package.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCHESTRATION_PACKAGE = REPO_ROOT / "cmm" / "orchestration"

#: Canonical owners Phase 11.2 must never redefine.
FORBIDDEN_OWNER_CLASSES = (
    "ProviderRegistry",
    "ProviderConnectionRegistry",
    "ProviderManifestRegistry",
    "ModelCatalog",
    "ModelRouteCatalog",
    "DomainRegistry",
    "AgentRegistry",
    "AgentRegistryService",
    "AgentResolver",
    "SessionStore",
    "FileSessionStore",
    "WorkflowEngine",
    "ValidationEngine",
    "KnowledgeStore",
    "MemoryStore",
    "EventBus",
    "EventRegistry",
    "ModelRouter",
    "ModelGateway",
    "Planner",
    "ToolRegistry",
    "AgentRuntime",
    "ExecutorRegistry",
    "DomainResolver",
    "DomainPermissionResolver",
    "DomainProfileResolver",
)

#: The genuinely new owners Phase 11.2 is allowed to define.
ALLOWED_NEW_OWNERS = (
    "OrchestrationDecisionRepository",
    "InMemoryOrchestrationDecisionRepository",
)

#: The frozen Phase 11.2 production module set.
FROZEN_MODULES = frozenset(
    {
        "__init__.py",
        "contracts.py",
        "errors.py",
        "intent.py",
        "context.py",
        "domain_router.py",
        "agent_router.py",
        "policy.py",
        "decision_repository.py",
        "events.py",
        "orchestrator.py",
        "platform_module.py",
    }
)

#: Canonical packages that must never import the orchestration layer.
CANONICAL_PACKAGE_ROOTS = (
    "domains",
    "agent_runtime",
    "validation",
    "workflows",
    "execution",
    "runtime",
    "platform",
    "cognitive",
    "memory",
    "planner",
)

#: Phase 11.3 Application Backend surfaces that Phase 11.2 must not introduce.
FORBIDDEN_API_TOKENS = (
    "fastapi",
    "flask",
    "starlette",
    "apirouter",
    "openapi",
    "@app.route",
    "@router.get",
    "@router.post",
    "conversationservice",
    "goalservice",
    "workflowservice",
    "knowledgeservice",
    "memoryservice",
    "configurationservice",
)

#: Provider / model routing surfaces that Phase 11.2 must not introduce.
FORBIDDEN_MODEL_TOKENS = (
    "modelgateway",
    "modelrouter",
    "kernel.llm.model_router",
    "provider_registry",
    "providerregistry",
    "routing policy engine",
)

#: Names that would function as hidden reasoning.
FORBIDDEN_REASONING_NAMES = (
    "chain_of_thought",
    "hidden_reasoning",
    "raw_reasoning",
    "reasoning_trace",
    "prompt",
    "provider_payload",
    "credential",
    "credentials",
    "secret",
)

#: Pure constructors that may legitimately run at module import time.
ALLOWED_IMPORT_TIME_CALLS = frozenset({"frozenset", "tuple", "list", "dict", "set"})

#: Expression shapes whose inner calls belong to a lazily evaluated scope.
_LAZY_SCOPES = (
    ast.GeneratorExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.Lambda,
)


def _package_files() -> list[Path]:
    return sorted(ORCHESTRATION_PACKAGE.glob("*.py"))


def _source_files() -> list[tuple[Path, str]]:
    return [(path, path.read_text()) for path in _package_files()]


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


# ── 1. No duplicate canonical owner ──────────────────────────────────────────


@pytest.mark.parametrize("owner", FORBIDDEN_OWNER_CLASSES)
def test_orchestration_defines_no_duplicate_canonical_owner(owner: str) -> None:
    offenders: list[str] = []

    for path in _package_files():
        for name in _defined_class_names(path):
            if name == owner or name.endswith(owner):
                offenders.append(f"{path.name}:{name}")

    assert not offenders, f"duplicate canonical owner defined: {offenders}"


def test_orchestration_new_owners_are_exactly_the_decision_repository() -> None:
    defined = {name for path in _package_files() for name in _defined_class_names(path)}

    repository_owners = {
        name for name in defined if name.endswith("DecisionRepository")
    }

    assert repository_owners == set(ALLOWED_NEW_OWNERS)


def test_orchestration_package_contains_only_the_frozen_modules() -> None:
    present = {path.name for path in ORCHESTRATION_PACKAGE.iterdir() if path.is_file()}

    assert present == FROZEN_MODULES


def test_no_parallel_orchestration_package_was_introduced() -> None:
    forbidden = (
        "orchestrator_runtime",
        "router_engine",
        "orchestration_store",
        "orchestration_runtime",
    )

    for name in forbidden:
        assert not (REPO_ROOT / "cmm" / name).exists(), (
            f"Phase 11.2 must not introduce the parallel package {name}"
        )


# ── 2. Dependency direction ──────────────────────────────────────────────────


def test_canonical_packages_do_not_import_orchestration() -> None:
    offenders: list[str] = []

    roots = [REPO_ROOT / "cmm" / package for package in CANONICAL_PACKAGE_ROOTS]
    roots.append(REPO_ROOT / "kernel")

    for root in roots:
        for path in sorted(root.rglob("*.py")):
            for module in _imported_modules(path):
                if module == "cmm.orchestration" or module.startswith(
                    "cmm.orchestration."
                ):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, f"reverse dependency onto cmm.orchestration: {offenders}"


def test_platform_package_does_not_import_orchestration() -> None:
    for path in sorted((REPO_ROOT / "cmm" / "platform").glob("*.py")):
        for module in _imported_modules(path):
            assert not module.startswith("cmm.orchestration"), (
                f"{path.name} must not import {module}"
            )


# ── 3. No Phase 11.3 API/backend leakage ─────────────────────────────────────


def test_orchestration_introduces_no_api_or_backend_surface() -> None:
    offenders: list[str] = []

    for path, source in _source_files():
        lowered = source.lower()
        for token in FORBIDDEN_API_TOKENS:
            if token in lowered:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"Phase 11.2 must not implement an API/backend: {offenders}"


def test_orchestration_imports_no_web_framework() -> None:
    for path in _package_files():
        for module in _imported_modules(path):
            root = module.split(".")[0]
            assert root not in {
                "fastapi",
                "flask",
                "starlette",
                "uvicorn",
                "aiohttp",
            }, f"{path.name} imports the web framework {module}"


# ── 4. No Model Gateway / provider routing ───────────────────────────────────


def test_orchestration_imports_no_model_or_provider_routing() -> None:
    for path in _package_files():
        for module in _imported_modules(path):
            assert not module.startswith("kernel.llm"), (
                f"{path.name} imports model infrastructure: {module}"
            )
            lowered = module.lower()
            for token in ("model_router", "model_gateway", "provider_registry"):
                assert token not in lowered, f"{path.name} imports {module}"


def test_orchestration_references_no_model_gateway_symbol() -> None:
    offenders: list[str] = []

    for path, source in _source_files():
        lowered = source.lower()
        for token in FORBIDDEN_MODEL_TOKENS:
            if token in lowered:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"Phase 11.2 must not route providers/models: {offenders}"


# ── 5. No import-time mutation ───────────────────────────────────────────────


def _module_body_offenders(path: Path) -> list[str]:
    """Return import-time statements that are neither declarations nor typing guards."""

    offenders: list[str] = []

    def inspect_statements(statements: list[ast.stmt], *, guarded: bool) -> None:
        for statement in statements:
            if isinstance(statement, ast.Expr):
                if not isinstance(statement.value, ast.Constant) or not isinstance(
                    statement.value.value, str
                ):
                    offenders.append(f"{path.name}:expression statement")
                continue
            if isinstance(statement, ast.If):
                if not guarded and not _is_type_checking_guard(statement):
                    offenders.append(f"{path.name}:module-level if")
                    continue
                inspect_statements(statement.body, guarded=True)
                continue
            if isinstance(
                statement,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Assign,
                    ast.AnnAssign,
                ),
            ):
                continue
            offenders.append(f"{path.name}:{type(statement).__name__}")

    inspect_statements(_parsed(path).body, guarded=False)
    return offenders


def _is_type_checking_guard(statement: ast.If) -> bool:
    """Return whether *statement* is the standard import-time typing guard."""

    test = statement.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Constant):
        return test.value is False
    return False


def _value_call_offenders(path: Path) -> list[str]:
    """Return impure calls evaluated while binding module-level values."""

    offenders: list[str] = []

    def inspect(expression: ast.AST) -> None:
        if isinstance(expression, ast.Call):
            callee = expression.func
            if isinstance(callee, ast.Name):
                name = callee.id
            elif isinstance(callee, ast.Attribute):
                name = callee.attr
            else:
                name = None
            if name not in ALLOWED_IMPORT_TIME_CALLS:
                offenders.append(f"{path.name}:{name}")
            inspect_children(expression.args)
            inspect_children(
                keyword.value
                for keyword in expression.keywords
                if keyword.value is not None
            )
            return
        inspect_children(ast.iter_child_nodes(expression))

    def inspect_children(nodes: object) -> None:
        for node in nodes:  # type: ignore[union-attr]
            if isinstance(node, ast.expr) and not isinstance(node, _LAZY_SCOPES):
                inspect(node)

    for statement in _parsed(path).body:
        value = getattr(statement, "value", None)
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and isinstance(
            value, ast.expr
        ):
            inspect(value)

    return offenders


def test_orchestration_module_bodies_have_no_side_effect_statement() -> None:
    """Only declarations may run at import time, never a mutating call."""

    offenders = [
        item for path in _package_files() for item in _module_body_offenders(path)
    ]

    assert not offenders, f"import-time side effects found: {offenders}"


def test_orchestration_module_level_values_are_pure_builders() -> None:
    """Module-level call expressions may only use pure constructors."""

    offenders = [
        item for path in _package_files() for item in _value_call_offenders(path)
    ]

    assert not offenders, f"impure module-level construction found: {offenders}"


def test_orchestration_modules_hold_no_service_singleton() -> None:
    import cmm.orchestration  # noqa: F401
    from cmm.orchestration.agent_router import CanonicalAgentRouter
    from cmm.orchestration.context import DefaultContextResolver
    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
    )
    from cmm.orchestration.domain_router import CanonicalDomainRouter
    from cmm.orchestration.events import RecordingOrchestrationEventSink
    from cmm.orchestration.intent import DeterministicIntentResolver
    from cmm.orchestration.orchestrator import Orchestrator
    from cmm.orchestration.policy import DefaultOrchestrationPolicy

    service_types = (
        CanonicalAgentRouter,
        DefaultContextResolver,
        InMemoryOrchestrationDecisionRepository,
        CanonicalDomainRouter,
        RecordingOrchestrationEventSink,
        DeterministicIntentResolver,
        Orchestrator,
        DefaultOrchestrationPolicy,
    )

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("cmm.orchestration"):
            continue
        assert isinstance(module, ModuleType)
        for attribute, value in vars(module).items():
            assert not isinstance(value, service_types), (
                f"{module_name}.{attribute} is a module-level service instance"
            )


def test_orchestration_package_does_no_file_io() -> None:
    for path in _package_files():
        for module in _imported_modules(path):
            root = module.split(".")[0]
            assert root not in {"os", "pathlib", "sqlite3", "tempfile", "pickle"}, (
                f"{path.name} performs file or database I/O through {module}"
            )


# ── 6. No hidden reasoning ───────────────────────────────────────────────────


def test_no_public_contract_exposes_a_hidden_reasoning_field() -> None:
    from cmm.orchestration import contracts, events

    public = (
        contracts.OrchestrationRequest,
        contracts.OrchestrationResult,
        contracts.OrchestrationDecisionRecord,
        contracts.IntentResolution,
        contracts.ResolvedContext,
        contracts.DomainRouteDecision,
        contracts.AgentRouteDecision,
        contracts.OrchestrationPolicyDecision,
        events.RecordedOrchestrationEvent,
    )

    for contract in public:
        names = {name.lower() for name in contract.__dataclass_fields__}
        for forbidden in FORBIDDEN_REASONING_NAMES:
            assert forbidden not in names, f"{contract.__name__}.{forbidden}"


def test_serialized_orchestration_values_never_carry_hidden_reasoning() -> None:
    from cmm.orchestration.contracts import (
        AgentRouteDecision,
        DomainRouteDecision,
        ExecutionRoute,
        IntentKind,
        IntentResolution,
        OrchestrationChannel,
        OrchestrationPolicyDecision,
        OrchestrationRequest,
        PolicyDisposition,
        ResolvedContext,
    )
    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
    )
    from cmm.orchestration.events import RecordingOrchestrationEventSink
    from cmm.orchestration.orchestrator import Orchestrator

    class _Intent:
        def resolve(self, request: OrchestrationRequest) -> IntentResolution:
            return IntentResolution(
                intent=IntentKind.QUESTION,
                needs_clarification=False,
                source_kind="structured_input",
            )

    class _Context:
        def resolve_base(self, request: OrchestrationRequest) -> ResolvedContext:
            return ResolvedContext(request_id=request.request_id, stage="base")

        def resolve_domain_context(self, request, base_context, domain_route):
            return ResolvedContext(request_id=request.request_id, stage="domain")

    class _Domain:
        def route_domain(self, request, intent, context) -> DomainRouteDecision:
            return DomainRouteDecision(
                status="resolved", primary_domain="domain:general"
            )

    class _Agent:
        def route_agent(
            self, *, request, intent, context, domain
        ) -> AgentRouteDecision:
            return AgentRouteDecision(route=ExecutionRoute.DIRECT_RESPONSE)

    class _Policy:
        def evaluate(self, *, request, intent, context, domain, route):
            return OrchestrationPolicyDecision(
                disposition=PolicyDisposition.ALLOW_ROUTE,
                reason_codes=("POLICY_ALLOWED",),
            )

    sink = RecordingOrchestrationEventSink()
    repository = InMemoryOrchestrationDecisionRepository()
    orchestrator = Orchestrator(
        intent_resolver=_Intent(),
        context_resolver=_Context(),
        domain_router=_Domain(),
        agent_router=_Agent(),
        policy=_Policy(),
        decision_repository=repository,
        event_sink=sink,
    )

    request = OrchestrationRequest(
        request_id="request-1",
        user_id="user-1",
        channel=OrchestrationChannel.CONVERSATION,
        session_id="session-1",
        input={"question": "What changed?"},
    )
    result = orchestrator.orchestrate(request)

    record = repository.get(result.decision_id)
    assert record is not None

    payloads = (
        json.dumps(result.to_dict(), sort_keys=True),
        json.dumps(request.to_dict(), sort_keys=True),
        json.dumps(record.to_dict(), sort_keys=True),
        json.dumps([event.to_dict() for event in sink.events()], sort_keys=True),
    )

    for payload in payloads:
        for forbidden in FORBIDDEN_REASONING_NAMES:
            assert forbidden not in payload, f"leaked {forbidden}: {payload}"


# ── 7. No runtime service locator ────────────────────────────────────────────


def test_orchestration_never_resolves_services_at_runtime() -> None:
    offenders: list[str] = []

    for path, source in _source_files():
        for token in (
            "ApplicationContainer",
            "IntegrationServiceRegistry",
            "get_service",
            "dependency_order",
        ):
            if token in source:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"runtime service locator usage: {offenders}"


def test_orchestrator_holds_exactly_the_frozen_collaborators() -> None:
    import inspect

    from cmm.orchestration.orchestrator import Orchestrator

    signature = inspect.signature(Orchestrator.__init__)
    assert [name for name in signature.parameters if name != "self"] == [
        "intent_resolver",
        "context_resolver",
        "domain_router",
        "agent_router",
        "policy",
        "decision_repository",
        "event_sink",
    ]


# ── 8. No new Event Bus, scheduler or queue ──────────────────────────────────


@pytest.mark.parametrize(
    "token", ["EventBus", "EventBroker", "EventRegistry", "EventDispatcher"]
)
def test_orchestration_defines_no_event_bus_owner(token: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if token in name
    ]

    assert not offenders, f"Phase 11.2 must not introduce an event bus: {offenders}"


@pytest.mark.parametrize("token", ["Scheduler", "Worker", "Queue", "ThreadPool"])
def test_orchestration_defines_no_scheduler_or_queue(token: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if token in name
    ]

    assert not offenders, f"Phase 11.2 must not introduce a scheduler: {offenders}"


# ── 9. Orchestration runtime roles are discriminating ────────────────────────


def _official_domain_router():
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.orchestration.domain_router import CanonicalDomainRouter

    return CanonicalDomainRouter(resolver=DefaultDomainResolver())


def test_official_domain_router_cannot_claim_the_agent_router_role() -> None:
    """Audit V1 MAJOR-01: distinct roles must not be structurally interchangeable."""

    from cmm.orchestration.agent_router import AgentRouter
    from cmm.orchestration.domain_router import DomainRouter

    router = _official_domain_router()

    assert isinstance(router, DomainRouter)
    assert not isinstance(router, AgentRouter)


def test_official_agent_router_cannot_claim_the_domain_router_role() -> None:
    """Audit V1 MAJOR-01: distinct roles must not be structurally interchangeable."""

    from cmm.orchestration.agent_router import AgentRouter, CanonicalAgentRouter
    from cmm.orchestration.domain_router import DomainRouter

    router = CanonicalAgentRouter()

    assert isinstance(router, AgentRouter)
    assert not isinstance(router, DomainRouter)


def _official_role_implementations() -> tuple[tuple[str, object, type], ...]:
    """Return every official implementation paired with its intended runtime role."""

    from cmm.orchestration.agent_router import AgentRouter, CanonicalAgentRouter
    from cmm.orchestration.context import ContextResolver, DefaultContextResolver
    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
        OrchestrationDecisionRepository,
    )
    from cmm.orchestration.domain_router import DomainRouter
    from cmm.orchestration.events import (
        OrchestrationEventSink,
        RecordingOrchestrationEventSink,
    )
    from cmm.orchestration.intent import (
        DeterministicIntentResolver,
        IntentResolver,
    )
    from cmm.orchestration.orchestrator import Orchestrator, OrchestratorProtocol
    from cmm.orchestration.policy import (
        DefaultOrchestrationPolicy,
        OrchestrationPolicy,
    )

    domain_router = _official_domain_router()
    agent_router = CanonicalAgentRouter()
    context_resolver = DefaultContextResolver(session_store=None)
    repository = InMemoryOrchestrationDecisionRepository()
    sink = RecordingOrchestrationEventSink()
    policy = DefaultOrchestrationPolicy()
    intent_resolver = DeterministicIntentResolver()
    orchestrator = Orchestrator(
        intent_resolver=intent_resolver,
        context_resolver=context_resolver,
        domain_router=domain_router,
        agent_router=agent_router,
        policy=policy,
        decision_repository=repository,
        event_sink=sink,
    )

    return (
        ("DeterministicIntentResolver", intent_resolver, IntentResolver),
        ("DefaultContextResolver", context_resolver, ContextResolver),
        ("CanonicalDomainRouter", domain_router, DomainRouter),
        ("CanonicalAgentRouter", agent_router, AgentRouter),
        ("DefaultOrchestrationPolicy", policy, OrchestrationPolicy),
        (
            "InMemoryOrchestrationDecisionRepository",
            repository,
            OrchestrationDecisionRepository,
        ),
        ("RecordingOrchestrationEventSink", sink, OrchestrationEventSink),
        ("Orchestrator", orchestrator, OrchestratorProtocol),
    )


def test_every_official_implementation_satisfies_its_intended_role() -> None:
    for label, implementation, intended in _official_role_implementations():
        assert isinstance(implementation, intended), (
            f"{label} must satisfy {intended.__name__}"
        )


def test_no_official_implementation_satisfies_another_orchestration_role() -> None:
    """Audit V1 MAJOR-01: stable orchestration roles are pairwise exclusive.

    A runtime Protocol check only verifies member presence, so an implementation
    satisfying two stable roles would still be cross-wirable.  Every official
    implementation must therefore satisfy exactly its own role.
    """

    implementations = _official_role_implementations()
    contracts = tuple(contract for _, _, contract in implementations)

    collisions: list[str] = []
    for label, implementation, intended in implementations:
        for contract in contracts:
            if contract is intended:
                continue
            if isinstance(implementation, contract):
                collisions.append(f"{label} -> {contract.__name__}")

    assert not collisions, (
        f"orchestration roles are not pairwise exclusive: {collisions}"
    )
