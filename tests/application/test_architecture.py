"""Phase 11.3 — executable architecture gates for the application core.

``cmm/application`` owns the public application semantics, so every gate here
protects the same property: the core is the *only* owner of the backend boundary
and it stays transport-neutral.

* **dependency direction** — no lower layer of the platform imports
  ``cmm.application`` or ``cmm.api``.  The design's forbidden set
  (``cmm.platform``, ``cmm.orchestration``, ``kernel``, ``cmm.domains``,
  ``cmm.agent_runtime``) is covered explicitly, and the whole platform tree is
  covered by the closing scan so a new package cannot silently acquire the
  dependency;
* **exact internal allowlist** — the core imports ``cmm.platform``,
  ``cmm.orchestration`` and one sanctioned canonical read/write adapter: the
  official session store of ``cmm.runtime.sessions``, used by
  ``SessionApplicationService`` only.  That single exemption is package-exact
  and is asserted to stay in one module;
* **transport neutrality** — the core imports no HTTP stack and no Pydantic.
  The public contracts stay dataclass-based and the transport DTOs stay in
  ``cmm.api``, which is what lets a second adapter reuse the same core;
* **no parallel owner** — the core defines no registry, event bus, model
  gateway, scheduler or plugin owner.  The one planned exception is the
  backend-owned idempotency repository, and the allowlist is exact: an
  ``ActiveRequestRepository`` was explicitly not required for v1;
* **no durable storage or migration layer** and **no provider or model
  routing** — the v1 backend is in-memory and local-first;
* **no second container** — the core consumes the Phase 11.1
  ``ApplicationContainer`` and introduces no container, locator or DI registry
  of its own;
* **no module-level service singleton** — the application is composed once and
  injected, never cached in a module global.

The transport-side half of the same gates lives in
``tests/api/test_architecture.py``.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLICATION_PACKAGE = REPO_ROOT / "cmm" / "application"
API_PACKAGE = REPO_ROOT / "cmm" / "api"

#: Packages the design places *above* every canonical lower layer.  Nothing
#: below them may import them.
PUBLIC_LAYERS = ("cmm.application", "cmm.api")

#: The sanctioned sibling consumers of the backend.  ``cmm.application`` owns the
#: boundary and ``cmm.api`` adapts it to HTTP; Phase 11.4 adds the public CLI
#: adapter as the third sanctioned consumer.  The approved Phase 11.4 design
#: places the CLI beside HTTP ("HTTP -> ApplicationGateway, CLI ->
#: ApplicationGateway"): it presents the same application boundary over another
#: transport and owns no platform truth of its own.  Nothing else in the tree
#: may import the backend, and this list stays exact — the guard below fails if
#: a listed module stops existing or stops importing the backend.
CLI_ADAPTER_MODULES = (
    REPO_ROOT / "cmm" / "cli_contracts.py",
    REPO_ROOT / "cmm" / "cli_application.py",
)

#: The conversational consumer of the application boundary: Phase 11.5
#: (DP-105) sanctions ``cmm.conversation`` as a consumer of the application
#: boundary (spec section 25, ``cmm.conversation -> cmm.application``).  The
#: package presents the conversational surface over the same backend and owns
#: no application authority of its own.  The exemption is deliberately a
#: *subtree* exemption — the closing scan skips every module under
#: ``cmm/conversation`` — so the same skip also lifts the ``cmm.api`` half of
#: the scan for the whole subtree.  That is why
#: ``test_the_conversation_package_exemption_is_live_and_honest`` below asserts
#: both halves of the bargain: the subtree really imports ``cmm.application``
#: and no module in it may import ``cmm.api`` (spec section 25 — the
#: conversation layer consumes the application boundary, never the HTTP
#: adapter).
CONVERSATION_PACKAGE = REPO_ROOT / "cmm" / "conversation"

#: Layers the design places below the application backend.
LOWER_LAYERS = (
    "cmm/platform",
    "cmm/orchestration",
    "cmm/domains",
    "cmm/agent_runtime",
    "cmm/validation",
    "cmm/workflows",
    "cmm/execution",
    "cmm/runtime",
    "cmm/cognitive",
    "cmm/memory",
    "cmm/planner",
    "kernel",
)

#: Exact allowlist of the internal packages the core may depend on.
ALLOWED_INTERNAL_IMPORTS = (
    "cmm.application",
    "cmm.platform",
    "cmm.orchestration",
)

#: The one sanctioned canonical adapter of the phase: the official session store
#: is the canonical session owner and ``SessionApplicationService`` is the
#: documented application-service adapter over it.  The exemption is exact — one
#: module, one package — so it can not silently spread to a second owner.
SANCTIONED_CANONICAL_ADAPTERS: dict[str, tuple[str, ...]] = {
    "sessions.py": ("cmm.runtime.sessions",),
}

#: Canonical subsystem packages the transport-neutral core must never name: they
#: own domain, agent, cognitive, execution, session and workflow authority, and
#: the application core adapts public requests without owning any of it.
CANONICAL_SUBSYSTEM_PACKAGES = (
    "cmm.agent_runtime",
    "cmm.cognitive",
    "cmm.domains",
    "cmm.execution",
    "cmm.runtime",
    "cmm.workflows",
)

#: The one composition root of the application package.  Phase 11.4 adds the
#: local runtime a standalone CLI starts from, and a composition root must name
#: every canonical component it wires — Phase 11.3 had no composition root, so
#: its core allowlists never had to describe one.  The exemption is exact and
#: additive: one module, canonical subsystem packages only.  Every other module
#: of the package keeps the frozen core allowlists, and
#: ``test_the_composition_root_exemption_stays_exact`` below keeps it that way.
COMPOSITION_ROOT_MODULES: dict[str, tuple[str, ...]] = {
    "local_runtime.py": CANONICAL_SUBSYSTEM_PACKAGES,
}

#: The external root the one composition root may name: ``kernel`` owns the
#: canonical provider registry the local graph binds.
COMPOSITION_ROOT_EXTERNAL_ROOTS = frozenset({"kernel"})

#: The one provider artefact the composition root may name: the canonical
#: provider registry it binds into the platform composition.  Binding a registry
#: is not routing — the composition root resolves no provider and selects no
#: model — and the transport-neutral core still may not name it at all.
COMPOSITION_ROOT_PROVIDER_MODULES = ("kernel.llm.provider_registry",)
COMPOSITION_ROOT_PROVIDER_SYMBOLS = ("ProviderRegistry",)

#: Exact allowlist of the standard-library roots the core may import.  A new
#: root is a new dependency of the transport-neutral core and must be frozen
#: here.  ``threading`` is frozen for exactly one use: the single private
#: in-process lock ``ApplicationGateway`` owns over the keyed idempotency
#: critical section.  No third-party dependency and no concurrency subsystem is
#: authorized by it.
ALLOWED_EXTERNAL_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "hashlib",
        "json",
        "math",
        "re",
        "threading",
        "types",
        "typing",
        "uuid",
    }
)

#: The HTTP stack and the serialization framework belong to the adapter, not to
#: the application core.
FORBIDDEN_TRANSPORT_IMPORT_ROOTS = (
    "aiohttp",
    "django",
    "fastapi",
    "flask",
    "httpx",
    "pydantic",
    "starlette",
    "uvicorn",
    "werkzeug",
)

#: Classes owned by canonical subsystems.  The application core must define no
#: competing owner for any of them.
FORBIDDEN_OWNER_CLASSES = (
    "DomainRegistry",
    "AgentRegistry",
    "ProviderRegistry",
    "WorkflowRegistry",
    "OperationRegistry",
    "EventBus",
    "EventStore",
    "ModelGateway",
    "RoutingPolicyEngine",
    "AuthService",
    "RBACEngine",
    "PluginRegistry",
    "PluginLoader",
    "MetricsStore",
    "BackupService",
    "WorkerPool",
    "TaskBroker",
    "Scheduler",
)

#: Owner-shaped suffixes: a class in the core that ends in one of these would be
#: a new authority, an event bus, a scheduler or a storage seam.
OWNER_SUFFIX_TOKENS = (
    "Registry",
    "Repository",
    "Store",
    "Bus",
    "Engine",
    "Loader",
    "Pool",
    "Broker",
    "Scheduler",
)

#: The exact new-owner allowlist of ``cmm/application``: the backend-owned
#: idempotency repository, and nothing else.  Cancellation and streaming were
#: implemented over the gateway, so no active-request repository exists.
ALLOWED_NEW_OWNER_CLASSES = frozenset(
    {
        "IdempotencyRepository",
        "InMemoryIdempotencyRepository",
    }
)

#: Module names that would introduce an owner, a durable storage layer, a
#: migration layer, an auth/RBAC layer or a plugin runtime by module alone.
FORBIDDEN_MODULE_NAMES = frozenset(
    {
        "auth.py",
        "bus.py",
        "container.py",
        "database.py",
        "db.py",
        "engine.py",
        "event_bus.py",
        "loader.py",
        "migrations.py",
        "plugins.py",
        "rbac.py",
        "registry.py",
        "resolver.py",
        "runtime.py",
        "scheduler.py",
        "store.py",
    }
)

#: Durable storage and migration drivers.  The v1 backend is in-memory.
FORBIDDEN_STORAGE_MODULES = (
    "aiosqlite",
    "alembic",
    "asyncpg",
    "psycopg",
    "psycopg2",
    "sqlalchemy",
    "sqlite3",
)

#: Directory names of a durable database or migration layer.
FORBIDDEN_STORAGE_DIRECTORIES = ("migrations", "alembic", "versions", "schema")

#: Provider and model routing surfaces: module fragments and imported symbols.
FORBIDDEN_ROUTING_MODULE_FRAGMENTS = (
    "provider_registry",
    "model_router",
    "model_gateway",
    "routing_policy",
    "model_catalog",
    "model_route",
)

FORBIDDEN_ROUTING_SYMBOLS = (
    "ProviderRegistry",
    "ModelRouter",
    "ModelGateway",
    "RoutingPolicyEngine",
)

#: Composition containers the design forbids Phase 11.3 from introducing: the
#: backend receives the ready Phase 11.1 ``ApplicationContainer`` instead.
FORBIDDEN_CONTAINER_CLASSES = (
    "BackendContainer",
    "APIContainer",
    "ServiceLocator",
    "DependencyContainer",
    "DIRegistry",
    "ApplicationRegistry",
)


def _package_files(package: Path = APPLICATION_PACKAGE) -> list[Path]:
    return sorted(package.glob("*.py"))


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


def _imported_symbols(path: Path) -> set[str]:
    symbols: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.ImportFrom):
            symbols.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            symbols.update(alias.asname or alias.name for alias in node.names)
    return symbols


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


# ── 1. Dependency direction: lower layers never import the backend ───────────


@pytest.mark.parametrize(
    "layer", LOWER_LAYERS, ids=lambda value: value.replace("/", "_")
)
def test_lower_layers_do_not_import_the_application_or_api_package(layer: str) -> None:
    offenders: list[str] = []

    for path in sorted((REPO_ROOT / layer).rglob("*.py")):
        for module in _imported_modules(path):
            for public in PUBLIC_LAYERS:
                if module == public or module.startswith(f"{public}."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        f"{layer} must not import the Phase 11.3 backend: {sorted(offenders)}"
    )


def test_only_the_backend_packages_and_the_cli_adapter_import_the_backend() -> None:
    """The whole platform tree closes the reverse dependency, not just a list."""

    offenders: list[str] = []

    for root in (REPO_ROOT / "cmm", REPO_ROOT / "kernel"):
        for path in sorted(root.rglob("*.py")):
            if APPLICATION_PACKAGE in path.parents or API_PACKAGE in path.parents:
                continue
            if CONVERSATION_PACKAGE in path.parents:
                continue
            if path in CLI_ADAPTER_MODULES:
                continue
            for module in _imported_modules(path):
                for public in PUBLIC_LAYERS:
                    if module == public or module.startswith(f"{public}."):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        "only cmm.api, cmm.application, cmm.conversation and the sanctioned "
        f"CLI adapter may import the backend: {sorted(offenders)}"
    )


def test_the_conversation_package_exemption_is_live_and_honest() -> None:
    """The conversation consumer exists, imports the backend and stays bounded.

    The exemption above may not go stale and may not exceed its sanction: the
    package must exist, at least one of its modules must really import
    ``cmm.application``, exactly as spec section 25 sanctions for Phase 11.5
    (DP-105) — and, because the same skip also lifts the ``cmm.api`` half of
    the closing scan for the whole subtree, no conversation module may import
    the HTTP adapter.
    """

    assert CONVERSATION_PACKAGE.is_dir(), (
        f"stale conversation exemption: {CONVERSATION_PACKAGE}"
    )

    imported = {
        module
        for path in sorted(CONVERSATION_PACKAGE.rglob("*.py"))
        for module in _imported_modules(path)
    }

    assert any(
        module == "cmm.application" or module.startswith("cmm.application.")
        for module in imported
    ), "no cmm.conversation module imports the application backend"

    api_importers = sorted(
        f"{path.relative_to(REPO_ROOT)} -> {module}"
        for path in sorted(CONVERSATION_PACKAGE.rglob("*.py"))
        for module in _imported_modules(path)
        if module == "cmm.api" or module.startswith("cmm.api.")
    )

    assert not api_importers, (
        "cmm.conversation must consume the application boundary, never the "
        f"HTTP adapter (spec section 25): {api_importers}"
    )


def test_the_sanctioned_cli_adapter_allowlist_is_exact_and_live() -> None:
    """Every allowlisted CLI module exists and really is a backend consumer."""

    for path in CLI_ADAPTER_MODULES:
        assert path.is_file(), f"stale CLI consumer allowlist entry: {path}"
        imported = _imported_modules(path)
        assert any(
            module == "cmm.application" or module.startswith("cmm.application.")
            for module in imported
        ), f"{path.relative_to(REPO_ROOT)} no longer imports the backend"


def test_application_package_internal_imports_are_the_frozen_allowlist() -> None:
    offenders: list[str] = []

    for path in _package_files():
        sanctioned = SANCTIONED_CANONICAL_ADAPTERS.get(path.name, ())
        composed = COMPOSITION_ROOT_MODULES.get(path.name, ())
        for module in _imported_modules(path):
            if not module.startswith("cmm."):
                continue
            allowed = ALLOWED_INTERNAL_IMPORTS + sanctioned + composed
            if not any(
                module == entry or module.startswith(f"{entry}.") for entry in allowed
            ):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, (
        "cmm.application may import cmm.platform, cmm.orchestration, its "
        "sanctioned canonical adapter and the one composition root's canonical "
        f"components only: {sorted(offenders)}"
    )


def test_the_composition_root_exemption_stays_exact() -> None:
    """One module is the composition root; the transport-neutral core stays pure.

    The set of application modules that name a canonical subsystem package must
    be exactly the sanctioned adapter plus the composition root, so the
    composition exemption can never spread silently to the core.
    """

    reachers = {
        path.name
        for path in _package_files()
        if any(
            module == package or module.startswith(f"{package}.")
            for module in _imported_modules(path)
            for package in (*CANONICAL_SUBSYSTEM_PACKAGES, "kernel")
        )
    }

    assert reachers == set(COMPOSITION_ROOT_MODULES) | set(
        SANCTIONED_CANONICAL_ADAPTERS
    ), f"unexpected canonical reach inside cmm.application: {sorted(reachers)}"


def test_canonical_session_adapter_exemption_stays_exact() -> None:
    """The one canonical adapter is used by exactly one application module."""

    users = {
        path.name
        for path in _package_files()
        if any(
            module == adapter or module.startswith(f"{adapter}.")
            for adapter in SANCTIONED_CANONICAL_ADAPTERS.get(path.name, ())
            for module in _imported_modules(path)
        )
    }

    assert users == set(SANCTIONED_CANONICAL_ADAPTERS), (
        f"only {sorted(SANCTIONED_CANONICAL_ADAPTERS)} may use the canonical "
        f"session store: {sorted(users)}"
    )


def test_application_package_external_imports_are_the_frozen_allowlist() -> None:
    offenders: list[str] = []

    for path in _package_files():
        composed = path.name in COMPOSITION_ROOT_MODULES
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root == "cmm":
                continue
            if root in ALLOWED_EXTERNAL_IMPORT_ROOTS:
                continue
            if composed and root in COMPOSITION_ROOT_EXTERNAL_ROOTS:
                continue
            offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"unfrozen application-core import: {sorted(offenders)}"


# ── 2. Transport neutrality ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "transport",
    FORBIDDEN_TRANSPORT_IMPORT_ROOTS,
    ids=lambda value: value,
)
def test_application_core_imports_no_transport_or_serialization_stack(
    transport: str,
) -> None:
    offenders = [
        f"{path.name} -> {module}"
        for path in _package_files()
        for module in _imported_modules(path)
        if module.split(".")[0] == transport
    ]

    assert not offenders, (
        f"the application core is transport-neutral, found {transport}: {offenders}"
    )


# ── 3. No parallel owner in the application core ─────────────────────────────


@pytest.mark.parametrize("owner", FORBIDDEN_OWNER_CLASSES)
def test_application_package_defines_no_parallel_owner_class(owner: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if name == owner or name.endswith(owner)
    ]

    assert not offenders, f"parallel owner defined in cmm.application: {offenders}"


def test_application_package_new_owner_classes_are_the_frozen_allowlist() -> None:
    """Only the backend-owned idempotency repository may be added in Phase 11.3."""

    defined = {name for path in _package_files() for name in _defined_class_names(path)}

    owner_shaped = {
        name
        for name in defined
        if any(name.endswith(token) for token in OWNER_SUFFIX_TOKENS)
    }

    assert owner_shaped == set(ALLOWED_NEW_OWNER_CLASSES), (
        "cmm.application may add the idempotency repository only: "
        f"{sorted(owner_shaped)}"
    )


def test_application_package_defines_no_active_request_repository() -> None:
    """Cancellation and streaming use the gateway, not a second request store."""

    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if "activerequest" in name.lower()
        or "requestrepository" in name.lower()
        or "requeststore" in name.lower()
    ]

    assert not offenders, (
        f"no active-request repository was required in v1: {sorted(offenders)}"
    )


def test_application_package_contains_no_owner_shaped_module() -> None:
    present = {path.name for path in _package_files()}

    offenders = sorted(present & FORBIDDEN_MODULE_NAMES)

    assert not offenders, (
        f"owner/storage/auth module introduced in cmm.application: {offenders}"
    )


@pytest.mark.parametrize("container", FORBIDDEN_CONTAINER_CLASSES)
def test_application_package_defines_no_second_container(container: str) -> None:
    """The backend consumes the Phase 11.1 container; it never replaces it."""

    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if name == container or name.endswith(container)
    ]

    assert not offenders, f"a second composition container was defined: {offenders}"


# ── 4. No durable storage or migration layer ─────────────────────────────────


def test_application_package_imports_no_durable_storage_driver() -> None:
    offenders: list[str] = []

    for path in _package_files():
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root in FORBIDDEN_STORAGE_MODULES:
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, (
        f"the v1 backend is in-memory and local-first: {sorted(offenders)}"
    )


@pytest.mark.parametrize(
    "package", [APPLICATION_PACKAGE, API_PACKAGE], ids=["application", "api"]
)
def test_phase_11_3_owns_no_migration_directory(package: Path) -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for name in FORBIDDEN_STORAGE_DIRECTORIES
        for path in package.rglob(name)
        if path.is_dir()
    ]

    assert not offenders, f"Phase 11.3 must not own migrations: {sorted(offenders)}"


# ── 5. No provider or model routing ──────────────────────────────────────────


def test_application_package_imports_no_provider_or_model_routing() -> None:
    offenders: list[str] = []

    for path in _package_files():
        composed = path.name in COMPOSITION_ROOT_MODULES
        for module in _imported_modules(path):
            if composed and module in COMPOSITION_ROOT_PROVIDER_MODULES:
                continue
            lowered = module.lower()
            for fragment in FORBIDDEN_ROUTING_MODULE_FRAGMENTS:
                if fragment in lowered:
                    offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"provider/model routing imported: {sorted(offenders)}"


def test_application_package_imports_no_provider_or_model_routing_symbol() -> None:
    offenders: list[str] = []

    for path in _package_files():
        composed = path.name in COMPOSITION_ROOT_MODULES
        symbols = _imported_symbols(path)
        if composed:
            symbols -= set(COMPOSITION_ROOT_PROVIDER_SYMBOLS)
        for symbol in symbols & set(FORBIDDEN_ROUTING_SYMBOLS):
            offenders.append(f"{path.name} -> {symbol}")

    assert not offenders, f"provider/model routing symbol imported: {sorted(offenders)}"


# ── 6. No module-level service singleton ─────────────────────────────────────


def test_application_modules_hold_no_service_singleton() -> None:
    """The backend is composed once and injected, never cached in a module."""

    from cmm.application.capabilities import CapabilityApplicationService
    from cmm.application.gateway import ApplicationGateway
    from cmm.application.health import HealthApplicationService
    from cmm.application.idempotency import InMemoryIdempotencyRepository
    from cmm.application.requests import RequestApplicationService
    from cmm.application.sessions import SessionApplicationService

    service_types = (
        ApplicationGateway,
        CapabilityApplicationService,
        HealthApplicationService,
        InMemoryIdempotencyRepository,
        RequestApplicationService,
        SessionApplicationService,
    )

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("cmm.application"):
            continue
        assert isinstance(module, ModuleType)
        for attribute, value in vars(module).items():
            assert not isinstance(value, service_types), (
                f"{module_name}.{attribute} is a module-level service singleton"
            )
