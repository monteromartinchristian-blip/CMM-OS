"""Phase 11.5 — conversation composition module tests.

``build_conversation_composition_module`` contributes the one Phase 11.5 service
binding — ``conversation.service`` — through the existing Phase 11.1
``StaticCompositionModule`` / ``ServiceBinding`` model.  It adds no composition
mechanism, changes no Phase 11.1 semantics and never constructs a subsystem: the
service is an already-built object supplied by the composition root.

These tests lock the frozen identities, the exact authority claim, the one
declared dependency on the application boundary (``application.gateway`` — never
backwards into a client, UI or CMMChat surface), the fail-closed role boundary,
the side-effect freedom of the contribution, the package's transport/UI
neutrality and the real composition of the service over the canonical local
application runtime and beside the closed Phase 11.2/11.3 contributions.

The fail-closed guard is proven load-bearing by mutation: the production module
is recompiled with exactly its ``isinstance`` guard excised, and the mutated
builder demonstrably accepts an impostor the real builder refuses — an impostor
that the registry then fails closed again through the binding's runtime
contract.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 6, 24, 25 and 26) and the committed Phase 11.5 plan.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationOperation,
    ApplicationStatus,
)
from cmm.application.local_runtime import (
    LocalApplicationRuntime,
    build_local_application_runtime,
)
from cmm.application.platform_module import (
    APPLICATION_AUTHORITY,
    APPLICATION_CONTRACT_VERSION,
    APPLICATION_MODULE_ID,
    APPLICATION_OWNER,
    APPLICATION_SCHEMA_VERSION,
    APPLICATION_SERVICE_ID,
    build_application_composition_module,
)
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.contracts import ConversationMessage, ConversationRole
from cmm.conversation.platform_module import (
    APPLICATION_GATEWAY_CONTRACT_VERSION,
    APPLICATION_GATEWAY_DEPENDENCY_ID,
    APPLICATION_GATEWAY_OWNER,
    APPLICATION_GATEWAY_SCHEMA_VERSION,
    CONVERSATION_AUTHORITY,
    CONVERSATION_CONTRACT_VERSION,
    CONVERSATION_MODULE_ID,
    CONVERSATION_OWNER,
    CONVERSATION_SCHEMA_VERSION,
    CONVERSATION_SERVICE_ID,
    build_conversation_composition_module,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import SharedSessionConversationAdapter
from cmm.orchestration.platform_module import (
    ORCHESTRATION_AUTHORITY,
    ORCHESTRATION_MODULE_ID,
    ORCHESTRATION_SERVICE_IDS,
    build_orchestration_composition_module,
)
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import (
    ContainerState,
    ServiceBinding,
    ServiceMode,
)
from cmm.platform.errors import IncompatibleContractError, MissingDependencyError
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_PACKAGE = REPO_ROOT / "cmm" / "conversation"
PLATFORM_MODULE_PATH = CONVERSATION_PACKAGE / "platform_module.py"

#: Import roots that would make the conversational boundary a UI or transport
#: owner.  The package consumes the application boundary and nothing above it.
FORBIDDEN_UI_IMPORT_ROOTS = (
    "PyQt5",
    "PyQt6",
    "PySide6",
    "aiohttp",
    "django",
    "fastapi",
    "flask",
    "gradio",
    "httpx",
    "pydantic",
    "starlette",
    "streamlit",
    "textual",
    "tkinter",
    "uvicorn",
    "werkzeug",
)

SESSION_ID = "session-conversation-1"
REQUEST_ID = "request-conversation-1"
USER_MESSAGE_ID = "user-message-1"
ASSISTANT_MESSAGE_ID = "assistant-message-1"
USER_CREATED_AT = "2026-09-17T10:00:00+00:00"
ASSISTANT_CREATED_AT = "2026-09-17T10:00:01+00:00"

#: The pinned public text of a canonical routed conversational outcome: a plain
#: conversational message is presented through the canonical ``question``
#: signal (remediation MAJOR-01), so the deterministic canonical resolver
#: classifies it as ``QUESTION`` and the canonical pipeline routes it.
ROUTED_TEXT = "The request was routed through the canonical application boundary."


# ── Canonical composition helpers ────────────────────────────────────────────


def _runtime() -> LocalApplicationRuntime:
    """Return one fresh canonical local application runtime."""

    return build_local_application_runtime()


def _conversation_service(runtime: LocalApplicationRuntime) -> ConversationService:
    """Compose the real conversational service over the canonical runtime."""

    return ConversationService(
        gateway=runtime.gateway,
        state=SharedSessionConversationAdapter(runtime.session_store),
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )


def _module() -> tuple[
    StaticCompositionModule, ConversationService, LocalApplicationRuntime
]:
    """Return the contribution, the bound service and the runtime behind it."""

    runtime = _runtime()
    service = _conversation_service(runtime)
    return build_conversation_composition_module(service=service), service, runtime


def _closed_phase_modules(
    runtime: LocalApplicationRuntime,
) -> tuple[StaticCompositionModule, StaticCompositionModule]:
    """Rebuild the closed Phase 11.2/11.3 contributions from the runtime.

    The application contribution binds the one real gateway and every
    orchestration collaborator is the canonical object the runtime's own
    container exposes, so the conversation binding composes beside the real
    Phase 11.2/11.3 services and never beside a stand-in.
    """

    container = runtime.container
    orchestration_module = build_orchestration_composition_module(
        intent_resolver=container.get_service("orchestration.intent_resolver"),
        context_resolver=container.get_service("orchestration.context_resolver"),
        domain_router=container.get_service("orchestration.domain_router"),
        agent_router=container.get_service("orchestration.agent_router"),
        policy=container.get_service("orchestration.policy"),
        decision_repository=container.get_service("orchestration.decision_repository"),
        event_sink=container.get_service("orchestration.event_sink"),
        orchestrator=container.get_service("orchestration.orchestrator"),
    )
    application_module = build_application_composition_module(gateway=runtime.gateway)
    return orchestration_module, application_module


def _backend_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            APPLICATION_SERVICE_ID,
            CONVERSATION_SERVICE_ID,
        ),
        enabled_modules=(
            ORCHESTRATION_MODULE_ID,
            APPLICATION_MODULE_ID,
            CONVERSATION_MODULE_ID,
        ),
    )


def _user_message() -> ConversationMessage:
    return ConversationMessage(
        id=USER_MESSAGE_ID,
        session_id=SESSION_ID,
        role=ConversationRole.USER,
        content="What changed in the plan?",
        created_at=USER_CREATED_AT,
    )


def _session_create_command() -> ApplicationCommand:
    return ApplicationCommand(
        request_id="request-conversation-create",
        api_version=APPLICATION_API_VERSION,
        operation=ApplicationOperation.SESSION_CREATE,
        channel=ApplicationChannel.CONVERSATION,
        payload={"session_id": SESSION_ID},
    )


# ── AST helpers ──────────────────────────────────────────────────────────────


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


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


def _called_names(path: Path) -> set[str]:
    called: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        if isinstance(callee, ast.Name):
            called.add(callee.id)
        elif isinstance(callee, ast.Attribute):
            called.add(callee.attr)
    return called


# ── Frozen identities ────────────────────────────────────────────────────────


def test_frozen_identifiers_are_stable() -> None:
    assert CONVERSATION_MODULE_ID == "phase11.conversation"
    assert CONVERSATION_SERVICE_ID == "conversation.service"
    assert CONVERSATION_OWNER == "cmm.conversation"
    assert CONVERSATION_CONTRACT_VERSION == "1.0.0"
    assert CONVERSATION_SCHEMA_VERSION == "1"
    assert CONVERSATION_AUTHORITY == "conversation-public-interface"
    assert APPLICATION_GATEWAY_DEPENDENCY_ID == "application.gateway"


# ── Contribution shape ───────────────────────────────────────────────────────


def test_module_is_a_static_composition_module_with_a_stable_identity() -> None:
    module, _service_object, _runtime_object = _module()

    assert isinstance(module, StaticCompositionModule)
    assert module.module_id == CONVERSATION_MODULE_ID


def test_module_contributes_exactly_one_service_binding() -> None:
    module, service, _runtime_object = _module()

    contributed = module.contribute(CompositionConfiguration())

    assert isinstance(contributed, tuple)
    assert len(contributed) == 1
    binding = contributed[0]
    assert isinstance(binding, ServiceBinding)
    assert binding.descriptor.service_id == CONVERSATION_SERVICE_ID
    assert binding.implementation is service


def test_binding_declares_its_boundary_and_enforceable_runtime_contract() -> None:
    module, service, _runtime_object = _module()

    binding = module.contribute(CompositionConfiguration())[0]

    assert binding.descriptor.contract.contract_name == CONVERSATION_SERVICE_ID
    assert binding.descriptor.contract.owner == CONVERSATION_OWNER
    assert binding.descriptor.contract.contract_version == CONVERSATION_CONTRACT_VERSION
    assert binding.descriptor.contract.schema_version == CONVERSATION_SCHEMA_VERSION
    assert binding.descriptor.mode is ServiceMode.LOCAL
    assert binding.runtime_contract is ConversationService
    assert isinstance(binding.implementation, binding.runtime_contract)
    implementation_type = type(service)
    assert binding.descriptor.implementation_id == (
        f"{implementation_type.__module__}.{implementation_type.__qualname__}"
    )


def test_only_the_conversation_service_claims_the_conversation_authority() -> None:
    module, _service_object, _runtime_object = _module()

    bindings = module.contribute(CompositionConfiguration())

    assert [binding.descriptor.authority for binding in bindings] == [
        CONVERSATION_AUTHORITY
    ]
    for binding in bindings:
        assert binding.descriptor.authority not in {
            "provider-registry",
            "domain-registry",
            "agent-registry",
            "workflow-registry",
            "execution-registry",
            "orchestration-request-coordinator",
            "application-public-gateway",
        }


def test_the_authority_is_distinct_from_the_other_composed_authorities() -> None:
    assert CONVERSATION_AUTHORITY != APPLICATION_AUTHORITY
    assert CONVERSATION_AUTHORITY != ORCHESTRATION_AUTHORITY


def test_no_duplicate_service_ids_in_the_module_or_across_the_closed_phases() -> None:
    module, _service_object, _runtime_object = _module()

    service_ids = [
        binding.descriptor.service_id
        for binding in module.contribute(CompositionConfiguration())
    ]

    assert service_ids == [CONVERSATION_SERVICE_ID]
    assert len(service_ids) == len(set(service_ids))
    assert CONVERSATION_SERVICE_ID not in set(ORCHESTRATION_SERVICE_IDS)
    assert CONVERSATION_SERVICE_ID != APPLICATION_SERVICE_ID
    assert CONVERSATION_MODULE_ID not in {
        ORCHESTRATION_MODULE_ID,
        APPLICATION_MODULE_ID,
    }


# ── The declared dependency edge ─────────────────────────────────────────────


def test_binding_declares_the_application_gateway_dependency() -> None:
    module, _service_object, _runtime_object = _module()

    binding = module.contribute(CompositionConfiguration())[0]
    dependencies = binding.descriptor.dependencies

    assert len(dependencies) == 1
    dependency = dependencies[0]
    assert dependency.service_id == APPLICATION_GATEWAY_DEPENDENCY_ID
    assert dependency.contract.contract_name == APPLICATION_GATEWAY_DEPENDENCY_ID
    assert dependency.contract.owner == APPLICATION_GATEWAY_OWNER
    assert dependency.contract.contract_version == APPLICATION_GATEWAY_CONTRACT_VERSION
    assert dependency.contract.schema_version == APPLICATION_GATEWAY_SCHEMA_VERSION


def test_declared_dependency_mirrors_the_phase_11_3_application_boundary() -> None:
    """The mirrored dependency contract can not silently drift from Phase 11.3."""

    assert APPLICATION_GATEWAY_DEPENDENCY_ID == APPLICATION_SERVICE_ID
    assert APPLICATION_GATEWAY_OWNER == APPLICATION_OWNER
    assert APPLICATION_GATEWAY_CONTRACT_VERSION == APPLICATION_CONTRACT_VERSION
    assert APPLICATION_GATEWAY_SCHEMA_VERSION == APPLICATION_SCHEMA_VERSION


def test_the_dependency_edge_points_at_the_application_boundary_never_a_client() -> (
    None
):
    module, _service_object, _runtime_object = _module()

    binding = module.contribute(CompositionConfiguration())[0]
    dependency_ids = tuple(
        dependency.service_id for dependency in binding.descriptor.dependencies
    )

    assert dependency_ids == (APPLICATION_GATEWAY_DEPENDENCY_ID,)
    # The composition graph may only ever point down into the platform; a
    # dependency named after a client, UI or CMMChat surface would be a
    # backwards edge and is refused here.
    for service_id in dependency_ids:
        lowered = service_id.lower()
        assert not any(
            fragment in lowered
            for fragment in ("cmma", "cmma.chat", "chat", "client", "ui.", "http")
        ), service_id


# ── Side-effect freedom and no new ownership ─────────────────────────────────


def test_module_contributes_nothing_until_it_is_invoked() -> None:
    registry = IntegrationServiceRegistry()

    _module()

    assert registry.service_ids() == ()


def test_building_the_module_never_mutates_the_bound_service() -> None:
    runtime = _runtime()
    service = _conversation_service(runtime)
    before = dict(vars(service))

    module = build_conversation_composition_module(service=service)

    assert dict(vars(service)) == before
    assert module.contribute(CompositionConfiguration())[0].implementation is service


def test_no_conversation_module_holds_a_service_singleton() -> None:
    _module()

    for module_name, module in list(sys.modules.items()):
        if module_name != "cmm.conversation" and not module_name.startswith(
            "cmm.conversation."
        ):
            continue
        assert isinstance(module, ModuleType)
        for attribute, value in vars(module).items():
            assert not isinstance(value, ConversationService), (
                f"{module_name}.{attribute} is a module-level service singleton"
            )


def test_importing_the_module_registers_nothing() -> None:
    program = (
        "import json\n"
        "import cmm.conversation.platform_module\n"
        "from cmm.platform.service_registry import IntegrationServiceRegistry\n"
        "print(json.dumps({'registered': len(IntegrationServiceRegistry())}))\n"
    )

    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {"registered": 0}


def test_the_module_defines_no_class_and_constructs_no_owner() -> None:
    defined = [
        node.name
        for node in ast.walk(_parsed(PLATFORM_MODULE_PATH))
        if isinstance(node, ast.ClassDef)
    ]

    assert defined == []

    constructed = _called_names(PLATFORM_MODULE_PATH) & {
        "ApplicationContainer",
        "ApplicationGateway",
        "ConversationRuntime",
        "ConversationService",
        "IntegrationServiceRegistry",
    }

    assert not constructed, (
        f"the contribution must construct no owner: {sorted(constructed)}"
    )


def test_the_module_imports_only_the_platform_package_and_its_own_package() -> None:
    imported = _imported_modules(PLATFORM_MODULE_PATH)
    cmm_imports = {
        module for module in imported if module == "cmm" or module.startswith("cmm.")
    }

    assert cmm_imports
    for module in sorted(cmm_imports):
        assert module.startswith(("cmm.platform", "cmm.conversation")), module
    for forbidden in ("cmm.application", "cmm.orchestration", "cmm.api"):
        assert not any(
            module == forbidden or module.startswith(f"{forbidden}.")
            for module in imported
        ), forbidden


def test_the_conversation_package_imports_no_ui_or_http_framework() -> None:
    offenders: list[str] = []

    for path in sorted(CONVERSATION_PACKAGE.rglob("*.py")):
        for module in _imported_modules(path):
            if module.split(".")[0] in FORBIDDEN_UI_IMPORT_ROOTS:
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        f"the conversational boundary is UI/transport neutral: {sorted(offenders)}"
    )


# ── Fail-closed role boundary ────────────────────────────────────────────────


class _DuckTypedService:
    """A service-shaped object that is not the concrete conversational service."""

    def submit(self, message: object, **kwargs: object) -> object:  # pragma: no cover
        raise AssertionError("an impostor service must never be composed")


@pytest.mark.parametrize(
    "candidate", [object(), None, "conversation.service", _DuckTypedService()]
)
def test_builder_rejects_a_non_service_object(candidate: object) -> None:
    with pytest.raises(TypeError):
        build_conversation_composition_module(service=candidate)  # type: ignore[arg-type]


def test_the_service_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        build_conversation_composition_module(_conversation_service(_runtime()))  # type: ignore[misc]


def _mutated_builder_without_the_guard() -> Callable[..., StaticCompositionModule]:
    """Compile the production module with exactly its fail-closed guard excised."""

    tree = _parsed(PLATFORM_MODULE_PATH)

    def is_fail_closed_guard(node: ast.stmt) -> bool:
        return (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.op, ast.Not)
            and isinstance(node.test.operand, ast.Call)
            and isinstance(node.test.operand.func, ast.Name)
            and node.test.operand.func.id == "isinstance"
            and any(isinstance(statement, ast.Raise) for statement in node.body)
        )

    excised = 0
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        kept = []
        for statement in node.body:
            if is_fail_closed_guard(statement):
                excised += 1
                continue
            kept.append(statement)
        node.body = kept

    assert excised == 1, "the builder must carry exactly one fail-closed guard"

    namespace: dict[str, object] = {"__name__": "mutated_conversation_platform_module"}
    # Executing our own mutated production source is the mutation itself.
    exec(compile(tree, str(PLATFORM_MODULE_PATH), "exec"), namespace)  # noqa: S102
    return namespace["build_conversation_composition_module"]  # type: ignore[return-value]


def test_mutation_proof_the_fail_closed_guard_is_load_bearing() -> None:
    """Excising the guard would silently compose an impostor; the guard stops it.

    The mutated module is the production source with exactly the guard removed,
    so the only difference between the real builder and the mutated one is the
    guard under test.
    """

    impostor = object()

    with pytest.raises(TypeError):
        build_conversation_composition_module(service=impostor)  # type: ignore[arg-type]

    mutated_builder = _mutated_builder_without_the_guard()
    forged_module = mutated_builder(service=impostor)
    forged_binding = forged_module.contribute(CompositionConfiguration())[0]

    # With the guard excised the unrelated object is accepted — so the guard,
    # not the binding model, is the load-bearing refusal...
    assert forged_binding.implementation is impostor
    assert not isinstance(forged_binding.implementation, ConversationService)

    # ...and the registry still fails the impostor closed through the binding's
    # runtime contract (defence in depth): an unrelated object can never claim
    # the conversational service identity.
    with pytest.raises(IncompatibleContractError):
        IntegrationServiceRegistry().register(forged_binding)


def test_an_unrelated_object_cannot_claim_the_conversation_identity() -> None:
    """A hand-built binding is still bounded by the declared runtime contract."""

    module, _service_object, _runtime_object = _module()
    original = module.contribute(CompositionConfiguration())[0]

    forged = ServiceBinding(
        descriptor=original.descriptor,
        implementation=object(),
        runtime_contract=original.runtime_contract,
    )

    with pytest.raises(IncompatibleContractError):
        IntegrationServiceRegistry().register(forged)


# ── Phase 11.1 integration ───────────────────────────────────────────────────


def test_missing_application_contribution_fails_closed() -> None:
    """The declared dependency is real: composing alone does not become ready."""

    module, _service_object, _runtime_object = _module()

    with pytest.raises(MissingDependencyError):
        ApplicationContainer.build(
            CompositionConfiguration(
                required_services=(CONVERSATION_SERVICE_ID,),
                enabled_modules=(CONVERSATION_MODULE_ID,),
            ),
            modules=(module,),
        )


def test_registry_accepts_the_contribution_and_validates_the_graph() -> None:
    module, _service_object, runtime = _module()
    orchestration_module, application_module = _closed_phase_modules(runtime)
    registry = IntegrationServiceRegistry()

    for contribution in (orchestration_module, application_module, module):
        for binding in contribution.contribute(CompositionConfiguration()):
            registry.register(binding)
    registry.validate_graph()

    service_ids = registry.service_ids()
    assert len(service_ids) == len(set(service_ids))
    order = registry.dependency_order()
    assert order.index(APPLICATION_GATEWAY_DEPENDENCY_ID) < order.index(
        CONVERSATION_SERVICE_ID
    )


def test_container_reaches_ready_with_the_conversation_contribution() -> None:
    module, service, runtime = _module()
    orchestration_module, application_module = _closed_phase_modules(runtime)

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(orchestration_module, application_module, module),
    )

    assert container.state is ContainerState.READY
    assert container.get_service(CONVERSATION_SERVICE_ID) is service


def test_ready_snapshot_projects_the_conversation_service_identity() -> None:
    module, _service_object, runtime = _module()
    orchestration_module, application_module = _closed_phase_modules(runtime)

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(orchestration_module, application_module, module),
    )

    payload = container.snapshot().to_dict()
    conversation = next(
        service
        for service in payload["services"]
        if service["service_id"] == CONVERSATION_SERVICE_ID
    )

    assert payload["state"] == "ready"
    assert conversation["owner"] == CONVERSATION_OWNER
    assert conversation["contract_version"] == CONVERSATION_CONTRACT_VERSION
    assert conversation["schema_version"] == CONVERSATION_SCHEMA_VERSION
    assert conversation["authority"] == CONVERSATION_AUTHORITY
    assert conversation["dependency_ids"] == [APPLICATION_GATEWAY_DEPENDENCY_ID]
    assert conversation["mode"] == "local"


def test_the_composed_service_serves_a_real_conversational_turn() -> None:
    """The composed service is the working conversational entrypoint."""

    module, service, runtime = _module()
    assert module.contribute(CompositionConfiguration())[0].implementation is service

    created = runtime.gateway.handle(_session_create_command())
    assert created.status is ApplicationStatus.SUCCESS
    envelope = runtime.session_store.load(SESSION_ID)
    assert envelope is not None

    response = service.submit(
        _user_message(),
        request_id=REQUEST_ID,
        expected_session_revision=envelope.revision,
        assistant_message_id=ASSISTANT_MESSAGE_ID,
        assistant_created_at=ASSISTANT_CREATED_AT,
    )

    assert response.message.role is ConversationRole.ASSISTANT
    assert response.message.id == ASSISTANT_MESSAGE_ID
    # A plain conversational message is presented through the canonical question
    # signal (remediation MAJOR-01), so the canonical deterministic resolver
    # routes it; the point is that the composed service really traversed the
    # canonical pipeline.
    assert response.message.content == ROUTED_TEXT

    state = SharedSessionConversationAdapter(runtime.session_store).load_conversation(
        SESSION_ID
    )
    assert state is not None
    assert state.messages == (_user_message(), response.message)
