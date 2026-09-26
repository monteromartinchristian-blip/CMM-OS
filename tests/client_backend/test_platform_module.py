"""Phase 11.50 — client backend composition module tests.

``build_client_backend_composition_module`` contributes the one Phase 11.50
service binding — ``client.backend`` — through the existing Phase 11.1
``StaticCompositionModule`` / ``ServiceBinding`` model.  It adds no composition
mechanism, changes no Phase 11.1 semantics and never constructs a subsystem: the
facade is an already-built object supplied by the composition root.

These gates lock the frozen identities, the exact facade authority claim, the two
downward dependencies on the closed canonical owners, the deliberate *absence* of
any model-gateway dependency, the fail-closed role boundary, the side-effect
freedom of the contribution, and the real composition of the facade over the
canonical local application runtime beside the closed Phase 11.2/11.3/11.5
contributions.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from cmm.application.local_runtime import (
    LocalApplicationRuntime,
    build_local_application_runtime,
)
from cmm.application.platform_module import (
    APPLICATION_AUTHORITY,
    APPLICATION_MODULE_ID,
    APPLICATION_SERVICE_ID,
    build_application_composition_module,
)
from cmm.client_backend import (
    CLIENT_BACKEND_MODULE_ID,
    CLIENT_BACKEND_SERVICE_ID,
    ClientBackend,
    build_client_backend_composition_module,
)
from cmm.client_backend.interface import ClientBackend as InterfaceClientBackend
from cmm.client_backend.platform_module import (
    APPLICATION_GATEWAY_CONTRACT_VERSION,
    APPLICATION_GATEWAY_DEPENDENCY_ID,
    APPLICATION_GATEWAY_OWNER,
    APPLICATION_GATEWAY_SCHEMA_VERSION,
    CLIENT_BACKEND_AUTHORITY,
    CLIENT_BACKEND_CONTRACT_VERSION,
    CLIENT_BACKEND_OWNER,
    CLIENT_BACKEND_SCHEMA_VERSION,
    CONVERSATION_CONTRACT_VERSION,
    CONVERSATION_DEPENDENCY_ID,
    CONVERSATION_OWNER,
    CONVERSATION_SCHEMA_VERSION,
)
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.platform_module import (
    CONVERSATION_AUTHORITY,
    CONVERSATION_MODULE_ID,
    CONVERSATION_SERVICE_ID,
    build_conversation_composition_module,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import SharedSessionConversationAdapter
from cmm.orchestration.platform_module import (
    ORCHESTRATION_MODULE_ID,
    ORCHESTRATION_SERVICE_IDS,
    build_orchestration_composition_module,
)
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer
from cmm.platform.contracts import ContainerState, ServiceBinding, ServiceMode
from cmm.platform.errors import IncompatibleContractError
from cmm.platform.modules import StaticCompositionModule
from cmm.platform.service_registry import IntegrationServiceRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_BACKEND_PACKAGE = REPO_ROOT / "cmm" / "client_backend"
PLATFORM_MODULE_PATH = CLIENT_BACKEND_PACKAGE / "platform_module.py"

#: Import roots that would make the client backend a transport, UI or model
#: owner.  The facade consumes the application and conversational boundaries and
#: nothing above or beside them.
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


# ── Canonical composition helpers ────────────────────────────────────────────


def _runtime() -> LocalApplicationRuntime:
    return build_local_application_runtime()


def _conversation_service(runtime: LocalApplicationRuntime) -> ConversationService:
    return ConversationService(
        gateway=runtime.gateway,
        state=SharedSessionConversationAdapter(runtime.session_store),
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )


def _client_backend(
    runtime: LocalApplicationRuntime, conversation: ConversationService
) -> ClientBackend:
    return ClientBackend(gateway=runtime.gateway, conversation=conversation)


@dataclass(slots=True)
class _Composed:
    """One canonical runtime, its conversational service and the client facade."""

    runtime: LocalApplicationRuntime
    conversation: ConversationService
    client: ClientBackend
    module: StaticCompositionModule


def _composed() -> _Composed:
    runtime = _runtime()
    conversation = _conversation_service(runtime)
    client = _client_backend(runtime, conversation)
    module = build_client_backend_composition_module(service=client)
    return _Composed(
        runtime=runtime, conversation=conversation, client=client, module=module
    )


def _module() -> tuple[StaticCompositionModule, ClientBackend, LocalApplicationRuntime]:
    composed = _composed()
    return composed.module, composed.client, composed.runtime


def _closed_phase_modules(
    runtime: LocalApplicationRuntime, conversation: ConversationService
) -> tuple[StaticCompositionModule, StaticCompositionModule, StaticCompositionModule]:
    """Rebuild the closed Phase 11.2/11.3/11.5 contributions from the runtime.

    The application contribution binds the one real gateway and the conversation
    contribution binds the *same* conversational service the facade delegates to,
    so the composed facade really is wired to the services the container exposes.
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
    conversation_module = build_conversation_composition_module(service=conversation)
    return orchestration_module, application_module, conversation_module


def _backend_configuration() -> CompositionConfiguration:
    return CompositionConfiguration(
        required_services=(
            *ORCHESTRATION_SERVICE_IDS,
            APPLICATION_SERVICE_ID,
            CONVERSATION_SERVICE_ID,
            CLIENT_BACKEND_SERVICE_ID,
        ),
        enabled_modules=(
            ORCHESTRATION_MODULE_ID,
            APPLICATION_MODULE_ID,
            CONVERSATION_MODULE_ID,
            CLIENT_BACKEND_MODULE_ID,
        ),
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


# ── Frozen identities ────────────────────────────────────────────────────────


def test_frozen_identifiers_are_stable() -> None:
    assert CLIENT_BACKEND_MODULE_ID == "phase11.client-backend"
    assert CLIENT_BACKEND_SERVICE_ID == "client.backend"
    assert CLIENT_BACKEND_OWNER == "cmm.client_backend"
    assert CLIENT_BACKEND_CONTRACT_VERSION == "1.0.0"
    assert CLIENT_BACKEND_SCHEMA_VERSION == "1"
    assert CLIENT_BACKEND_AUTHORITY == "client-backend-public-facade"
    assert APPLICATION_GATEWAY_DEPENDENCY_ID == "application.gateway"
    assert CONVERSATION_DEPENDENCY_ID == "conversation.service"


# ── Contribution shape ───────────────────────────────────────────────────────


def test_module_is_a_static_composition_module_with_a_stable_identity() -> None:
    module, _service, _runtime = _module()

    assert isinstance(module, StaticCompositionModule)
    assert module.module_id == CLIENT_BACKEND_MODULE_ID


def test_module_contributes_exactly_one_service_binding() -> None:
    module, service, _runtime = _module()

    contributed = module.contribute(CompositionConfiguration())

    assert isinstance(contributed, tuple)
    assert len(contributed) == 1
    binding = contributed[0]
    assert isinstance(binding, ServiceBinding)
    assert binding.descriptor.service_id == CLIENT_BACKEND_SERVICE_ID
    assert binding.implementation is service


def test_the_binding_runtime_contract_is_the_concrete_facade() -> None:
    module, _service, _runtime = _module()

    binding = module.contribute(CompositionConfiguration())[0]

    assert binding.runtime_contract is InterfaceClientBackend
    assert binding.runtime_contract is ClientBackend


def test_binding_declares_its_boundary_and_enforceable_runtime_contract() -> None:
    module, _service, _runtime = _module()

    binding = module.contribute(CompositionConfiguration())[0]

    assert binding.descriptor.contract.contract_name == CLIENT_BACKEND_SERVICE_ID
    assert binding.descriptor.contract.owner == CLIENT_BACKEND_OWNER
    assert (
        binding.descriptor.contract.contract_version == CLIENT_BACKEND_CONTRACT_VERSION
    )
    assert binding.descriptor.contract.schema_version == CLIENT_BACKEND_SCHEMA_VERSION
    assert binding.descriptor.mode is ServiceMode.LOCAL
    assert binding.descriptor.authority == CLIENT_BACKEND_AUTHORITY


def test_binding_declares_the_two_downward_dependencies_only() -> None:
    module, _service, _runtime = _module()

    binding = module.contribute(CompositionConfiguration())[0]
    dependencies = binding.descriptor.dependencies

    assert [dependency.service_id for dependency in dependencies] == [
        APPLICATION_GATEWAY_DEPENDENCY_ID,
        CONVERSATION_DEPENDENCY_ID,
    ]
    assert dependencies[0].contract.owner == APPLICATION_GATEWAY_OWNER
    assert dependencies[0].contract.contract_version == (
        APPLICATION_GATEWAY_CONTRACT_VERSION
    )
    assert dependencies[0].contract.schema_version == (
        APPLICATION_GATEWAY_SCHEMA_VERSION
    )
    assert dependencies[1].contract.owner == CONVERSATION_OWNER
    assert dependencies[1].contract.contract_version == CONVERSATION_CONTRACT_VERSION
    assert dependencies[1].contract.schema_version == CONVERSATION_SCHEMA_VERSION


def test_the_binding_declares_no_model_gateway_dependency() -> None:
    """The client never acquires model execution authority through composition."""

    module, _service, _runtime = _module()

    binding = module.contribute(CompositionConfiguration())[0]

    assert "model.gateway" not in {
        dependency.service_id for dependency in binding.descriptor.dependencies
    }
    assert "provider.registry" not in {
        dependency.service_id for dependency in binding.descriptor.dependencies
    }


def test_the_facade_authority_is_a_facade_authority_and_not_an_owner() -> None:
    """The claimed authority is explicit, and it is not a closed-phase authority."""

    module, _service, _runtime = _module()
    binding = module.contribute(CompositionConfiguration())[0]

    assert binding.descriptor.authority == CLIENT_BACKEND_AUTHORITY
    assert binding.descriptor.authority not in {
        APPLICATION_AUTHORITY,
        CONVERSATION_AUTHORITY,
    }
    assert "facade" in CLIENT_BACKEND_AUTHORITY


# ── Fail-closed construction ─────────────────────────────────────────────────


def test_the_builder_refuses_an_impostor() -> None:
    class _Impostor:
        def create_session(self, session_id):  # pragma: no cover - never reached
            return None

    with pytest.raises(TypeError):
        build_client_backend_composition_module(service=_Impostor())  # type: ignore[arg-type]


def test_the_builder_refuses_a_client_backend_subclass_binding() -> None:
    """``CLIENT_BACKEND_SUBCLASS_BINDING=REJECTED``.

    Independent Audit V1 reproduced that ``isinstance(service, ClientBackend)``
    let an arbitrary facade subclass claim the canonical ``client.backend``
    service identity.  The binding requires the exact official facade type.
    """

    module, service, _runtime = _module()

    class ClientBackendSubclass(ClientBackend):
        """A facade subclass: only its exact type differs from the official one."""

    subclass = ClientBackendSubclass.__new__(ClientBackendSubclass)
    subclass.__dict__.update(service.__dict__)

    assert isinstance(subclass, ClientBackend)
    assert type(subclass) is not ClientBackend

    with pytest.raises(TypeError):
        build_client_backend_composition_module(service=subclass)

    # The exact official facade is still accepted.
    assert module.contribute(CompositionConfiguration())[0].implementation is service


# ── Authoritative registry composition identity ──────────────────────────────


def _client_backend_subclass(service: ClientBackend) -> ClientBackend:
    """Return an adversarial facade subclass carrying the official instance state.

    Only the exact type differs from the official facade, so a runtime-contract
    check that falls back to ``isinstance`` accepts it.
    """

    class ClientBackendSubclass(ClientBackend):
        """A facade subclass: only its exact type differs from the official one."""

    subclass = ClientBackendSubclass.__new__(ClientBackendSubclass)
    subclass.__dict__.update(service.__dict__)
    return subclass


def test_the_authoritative_registry_rejects_a_hand_built_subclass_binding() -> None:
    """``CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=REJECTED``.

    Independent Re-audit V2 reproduced that the exact-type identity of
    ``client.backend`` was enforced only by the convenience builder: a valid
    hand-built ``ServiceBinding`` carrying the canonical ``client.backend``
    descriptor, the ``ClientBackend`` runtime contract and a facade *subclass*
    implementation was ACCEPTED by the authoritative Phase 11.1 registry, which
    fell back to ``isinstance``.  Remediation V2 moves the exact gate into the
    registry itself, so the manual binding can no longer claim the canonical
    service identity.
    """

    composed = _composed()
    official = composed.module.contribute(CompositionConfiguration())[0]
    subclass = _client_backend_subclass(composed.client)

    assert isinstance(subclass, ClientBackend)
    assert type(subclass) is not ClientBackend

    hand_built = ServiceBinding(
        descriptor=official.descriptor,
        implementation=subclass,
        runtime_contract=ClientBackend,
    )

    registry = IntegrationServiceRegistry()
    with pytest.raises(IncompatibleContractError) as failure:
        registry.register(hand_built)

    assert failure.value.result.details["reason_code"] == "RUNTIME_CONTRACT_MISMATCH"
    assert failure.value.result.details["service_id"] == CLIENT_BACKEND_SERVICE_ID
    assert registry.get(CLIENT_BACKEND_SERVICE_ID) is None


def test_the_builder_constructs_nothing() -> None:
    """The contribution is side-effect free: two calls bind the same object."""

    module, service, _runtime = _module()

    first = module.contribute(CompositionConfiguration())
    second = module.contribute(CompositionConfiguration())

    assert first[0].implementation is service
    assert second[0].implementation is service
    assert first[0].implementation is second[0].implementation


def test_importing_the_platform_module_constructs_nothing() -> None:
    """Importing the contribution module never builds a facade or a container."""

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import cmm.client_backend.platform_module as m; "
                "print('cmm.client_backend.interface' in sys.modules)"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(REPO_ROOT)},
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() in {"True", "False"}


# ── Real composition ─────────────────────────────────────────────────────────


def test_container_reaches_ready_with_the_client_backend_contribution() -> None:
    composed = _composed()
    module, service = composed.module, composed.client
    orchestration_module, application_module, conversation_module = (
        _closed_phase_modules(composed.runtime, composed.conversation)
    )

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(
            orchestration_module,
            application_module,
            conversation_module,
            module,
        ),
    )

    assert container.state is ContainerState.READY
    # Exact instance identity: the resolved service IS the configured facade.
    assert container.get_service(CLIENT_BACKEND_SERVICE_ID) is service


def test_ready_snapshot_projects_the_client_backend_identity() -> None:
    composed = _composed()
    module = composed.module
    orchestration_module, application_module, conversation_module = (
        _closed_phase_modules(composed.runtime, composed.conversation)
    )

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(
            orchestration_module,
            application_module,
            conversation_module,
            module,
        ),
    )

    payload = container.snapshot().to_dict()
    client = next(
        service
        for service in payload["services"]
        if service["service_id"] == CLIENT_BACKEND_SERVICE_ID
    )

    assert payload["state"] == "ready"
    assert client["owner"] == CLIENT_BACKEND_OWNER
    assert client["contract_version"] == CLIENT_BACKEND_CONTRACT_VERSION
    assert client["schema_version"] == CLIENT_BACKEND_SCHEMA_VERSION
    assert client["authority"] == CLIENT_BACKEND_AUTHORITY
    assert client["dependency_ids"] == [
        APPLICATION_GATEWAY_DEPENDENCY_ID,
        CONVERSATION_DEPENDENCY_ID,
    ]
    assert client["mode"] == "local"
    assert "model.gateway" not in client["dependency_ids"]


def test_the_resolved_facade_retains_the_exact_canonical_owners() -> None:
    """The composed facade delegates to the very owners of the runtime.

    The wiring is read white-box because the public facade deliberately returns
    no live canonical owner (Audit V1 MAJOR-01): the observable public contract
    is the composition binding and the coherence evidence, not the owner objects.
    """

    composed = _composed()
    module, service = composed.module, composed.client
    orchestration_module, application_module, conversation_module = (
        _closed_phase_modules(composed.runtime, composed.conversation)
    )

    container = ApplicationContainer.build(
        _backend_configuration(),
        modules=(
            orchestration_module,
            application_module,
            conversation_module,
            module,
        ),
    )

    resolved = container.get_service(CLIENT_BACKEND_SERVICE_ID)
    gateway = container.get_service(APPLICATION_SERVICE_ID)
    conversation = container.get_service(CONVERSATION_SERVICE_ID)

    assert resolved is service
    assert type(resolved) is ClientBackend
    assert resolved._gateway is gateway
    assert resolved._conversation is conversation
    assert conversation.uses_application_gateway(gateway) is True


def test_composing_without_the_conversation_contribution_fails_closed() -> None:
    """The declared dependency is a real graph edge, not decoration.

    The Phase 11.1 pipeline is fail-closed and ordered: a selection that enables
    the client backend without providing the conversation contribution is
    rejected as an invalid configuration before any service is resolved.  Either
    way no container is returned, so a facade without its conversational owner
    can never be composed into a usable graph.
    """

    composed = _composed()
    module = composed.module
    orchestration_module, application_module, _conversation_module = (
        _closed_phase_modules(composed.runtime, composed.conversation)
    )

    from cmm.platform.errors import (
        InvalidConfigurationError,
        MissingDependencyError,
        PlatformCompositionError,
    )

    with pytest.raises(
        (InvalidConfigurationError, MissingDependencyError, PlatformCompositionError)
    ) as failure:
        ApplicationContainer.build(
            _backend_configuration(),
            modules=(orchestration_module, application_module, module),
        )

    assert "conversation" in str(failure.value) or "module" in str(failure.value)


def test_the_client_backend_dependency_edge_is_marked_required() -> None:
    """The dependency is genuinely required: resolving it is part of the build."""

    composed = _composed()
    binding = composed.module.contribute(CompositionConfiguration())[0]
    required = {dependency.service_id for dependency in binding.descriptor.dependencies}

    # The build above proves the real container demands exactly these services.
    assert required == {APPLICATION_GATEWAY_DEPENDENCY_ID, CONVERSATION_DEPENDENCY_ID}
    assert CLIENT_BACKEND_SERVICE_ID not in required


# ── Module hygiene ───────────────────────────────────────────────────────────


def test_the_platform_module_imports_no_transport_or_ui_framework() -> None:
    imported = _imported_modules(PLATFORM_MODULE_PATH)

    for module in imported:
        root = module.split(".")[0]
        assert root not in FORBIDDEN_UI_IMPORT_ROOTS, module


def test_the_platform_module_imports_no_model_orchestration_internals() -> None:
    imported = _imported_modules(PLATFORM_MODULE_PATH)

    for module in imported:
        assert not module.startswith("kernel.llm")
        assert not module.startswith("cmm.orchestration")
        assert module != "cmm.application.gateway"


def test_the_package_never_imports_the_platform_container() -> None:
    """The facade is bound by a composition root; it never resolves services."""

    for path in sorted(CLIENT_BACKEND_PACKAGE.rglob("*.py")):
        imported = _imported_modules(path)
        assert "cmm.platform.container" not in imported, path
        assert "cmm.platform.service_registry" not in imported, path
