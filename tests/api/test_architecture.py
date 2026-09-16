"""Phase 11.3 — executable architecture gates for the v1 HTTP adapter.

``cmm.api`` is the transport adapter, so every gate here protects the same
property: the adapter adapts, it never becomes a second owner and it never
reaches past the application layer.

* **dependency direction** — the adapter imports ``cmm.application`` and the
  HTTP stack, nothing else.  The plan's frozen owner list (``cmm.domains``,
  ``cmm.agent_runtime``, ``cmm.runtime.sessions``, ``kernel.llm``,
  ``cmm.workflows``, ``cmm.execution``, ``cmm.validation``) is forbidden, and so
  are the remaining bypasses of the design's allowed direction (``cmm.platform``,
  ``cmm.orchestration``, ``kernel``): no request may reach an orchestrator, a
  registry or a session store without passing through the application gateway.
  There is no dynamic import or reflected dispatch either, because a string
  dispatch would make the static gate unverifiable;
* **no reverse dependency** — no lower layer of the platform imports
  ``cmm.api``;
* **no parallel owner** — the adapter defines no registry, repository, event
  bus, model gateway, scheduler or plugin owner, and no ``ActiveRequestRepository``
  was introduced to support cancellation or streaming;
* **no durable storage** — no database driver import and no migration directory,
  because the v1 backend is in-memory and local-first;
* **no provider or model routing** — the adapter never reaches model
  infrastructure, directly or through a transitively named module;
* **no module-level service singleton** — two applications built from two
  gateways stay independent, which the OpenAPI determinism test also requires.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PACKAGE = REPO_ROOT / "cmm" / "api"

#: The canonical owners and session authority the adapter must never reach.
#: This is the frozen list of the Phase 11.3 implementation plan.
FORBIDDEN_CANONICAL_IMPORTS = (
    "cmm.domains",
    "cmm.agent_runtime",
    "cmm.runtime.sessions",
    "kernel.llm",
    "cmm.workflows",
    "cmm.execution",
    "cmm.validation",
)

#: The remaining bypasses of the design's allowed direction
#: (``cmm.api -> cmm.application -> cmm.platform/cmm.orchestration``).  Platform
#: and orchestration imports would let a transport handler bind or drive a
#: composition directly, so the adapter must not import them either.
FORBIDDEN_BYPASS_IMPORTS = (
    "cmm.platform",
    "cmm.orchestration",
    "kernel",
)

#: Every internal import the adapter may perform.
FORBIDDEN_API_IMPORTS = FORBIDDEN_CANONICAL_IMPORTS + FORBIDDEN_BYPASS_IMPORTS

#: Exact allowlist of the internal packages the adapter depends on.
ALLOWED_INTERNAL_IMPORTS = ("cmm.api", "cmm.application")

#: Exact allowlist of the standard-library and HTTP-stack roots the adapter may
#: import.  A new root is a new transport dependency and must be frozen here.
ALLOWED_EXTERNAL_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "collections",
        "fastapi",
        "json",
        "pydantic",
        "starlette",
        "typing",
        "uuid",
    }
)

#: Classes owned by canonical subsystems.  The transport adapter must define no
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

#: Owner-shaped suffixes: a class in the adapter that ends in one of these would
#: be a new authority, an event bus, a scheduler or a storage seam.
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

#: The exact new-owner allowlist of ``cmm.api``: the transport adapter owns no
#: new authority at all.  The application-owned idempotency repository is the
#: one planned exception of the phase and is locked in
#: ``tests/application/test_architecture.py``; a cancellation or streaming
#: request repository was explicitly not required.
ALLOWED_NEW_OWNER_CLASSES: frozenset[str] = frozenset()

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

#: Layers the design places below the application backend.  None of them may
#: import ``cmm.api``.
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

#: String dispatch would make every static gate above unverifiable.
FORBIDDEN_DISPATCH_TOKENS = ("import_module", "__import__", "getattr")


def _package_files(package: Path) -> list[Path]:
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


# ── 1. Dependency direction: the adapter adapts, it does not reach owners ─────


@pytest.mark.parametrize(
    "forbidden", FORBIDDEN_API_IMPORTS, ids=lambda value: value.replace(".", "_")
)
def test_api_package_imports_no_lower_layer_or_canonical_owner(forbidden: str) -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for module in _imported_modules(path):
            if module == forbidden or module.startswith(f"{forbidden}."):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, (
        f"cmm.api must reach {forbidden} through the application layer only: "
        f"{sorted(offenders)}"
    )


def test_api_package_internal_imports_are_the_application_layer_only() -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for module in _imported_modules(path):
            if not module.startswith("cmm."):
                continue
            if not any(
                module == allowed or module.startswith(f"{allowed}.")
                for allowed in ALLOWED_INTERNAL_IMPORTS
            ):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, (
        "the v1 adapter may import cmm.api and cmm.application only: "
        f"{sorted(offenders)}"
    )


def test_api_package_transport_imports_are_the_frozen_allowlist() -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root == "cmm":
                continue
            if root not in ALLOWED_EXTERNAL_IMPORT_ROOTS:
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"unfrozen transport import in cmm.api: {sorted(offenders)}"


def test_api_package_never_dispatches_by_string_or_reflection() -> None:
    """Scenario M: no bypass may be hidden behind dynamic dispatch."""

    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        source = path.read_text()
        for token in FORBIDDEN_DISPATCH_TOKENS:
            if token in source:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, (
        f"the adapter must dispatch on explicit contracts only: {offenders}"
    )


@pytest.mark.parametrize(
    "layer", LOWER_LAYERS, ids=lambda value: value.replace("/", "_")
)
def test_lower_layers_do_not_import_the_api_package(layer: str) -> None:
    offenders: list[str] = []

    for path in sorted((REPO_ROOT / layer).rglob("*.py")):
        for module in _imported_modules(path):
            if module == "cmm.api" or module.startswith("cmm.api."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, f"{layer} must not import cmm.api: {sorted(offenders)}"


# ── 2. No parallel owner in the transport adapter ────────────────────────────


@pytest.mark.parametrize("owner", FORBIDDEN_OWNER_CLASSES)
def test_api_package_defines_no_parallel_owner_class(owner: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files(API_PACKAGE)
        for name in _defined_class_names(path)
        if name == owner or name.endswith(owner)
    ]

    assert not offenders, f"parallel owner defined in cmm.api: {sorted(offenders)}"


def test_api_package_new_owner_classes_are_the_frozen_allowlist() -> None:
    """The adapter owns no new authority: the allowlist is empty."""

    defined = {
        name
        for path in _package_files(API_PACKAGE)
        for name in _defined_class_names(path)
    }

    owner_shaped = {
        name
        for name in defined
        if any(name.endswith(token) for token in OWNER_SUFFIX_TOKENS)
    }

    assert owner_shaped == set(ALLOWED_NEW_OWNER_CLASSES), (
        f"cmm.api may not introduce an owner: {sorted(owner_shaped)}"
    )


def test_api_package_defines_no_active_request_repository() -> None:
    """Cancellation and streaming use the gateway, not a second request store."""

    offenders = [
        f"{path.name}:{name}"
        for path in _package_files(API_PACKAGE)
        for name in _defined_class_names(path)
        if "activerequest" in name.lower()
        or "requestrepository" in name.lower()
        or "requeststore" in name.lower()
    ]

    assert not offenders, (
        f"no active-request repository was required in v1: {sorted(offenders)}"
    )


def test_api_package_contains_no_owner_shaped_module() -> None:
    present = {path.name for path in _package_files(API_PACKAGE)}

    offenders = sorted(present & FORBIDDEN_MODULE_NAMES)

    assert not offenders, (
        f"owner/storage/auth module introduced in cmm.api: {offenders}"
    )


# ── 3. No durable storage or migration layer ─────────────────────────────────


def test_api_package_imports_no_durable_storage_driver() -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if root in FORBIDDEN_STORAGE_MODULES:
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, (
        f"the v1 backend is in-memory and local-first: {sorted(offenders)}"
    )


def test_api_package_owns_no_migration_directory() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for name in FORBIDDEN_STORAGE_DIRECTORIES
        for path in API_PACKAGE.rglob(name)
        if path.is_dir()
    ]

    assert not offenders, f"Phase 11.3 must not own migrations: {sorted(offenders)}"


# ── 4. No provider or model routing ──────────────────────────────────────────


def test_api_package_imports_no_provider_or_model_routing() -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for module in _imported_modules(path):
            lowered = module.lower()
            for fragment in FORBIDDEN_ROUTING_MODULE_FRAGMENTS:
                if fragment in lowered:
                    offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"provider/model routing imported: {sorted(offenders)}"


def test_api_package_imports_no_provider_or_model_routing_symbol() -> None:
    offenders: list[str] = []

    for path in _package_files(API_PACKAGE):
        for symbol in _imported_symbols(path) & set(FORBIDDEN_ROUTING_SYMBOLS):
            offenders.append(f"{path.name} -> {symbol}")

    assert not offenders, f"provider/model routing symbol imported: {sorted(offenders)}"


# ── 5. No module-level service singleton ─────────────────────────────────────


def test_api_modules_hold_no_service_singleton() -> None:
    """Two applications built from two gateways must stay independent."""

    from cmm.application import ApplicationGateway

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("cmm.api"):
            continue
        assert isinstance(module, ModuleType)
        for attribute, value in vars(module).items():
            assert not isinstance(value, ApplicationGateway), (
                f"{module_name}.{attribute} caches a gateway instance"
            )
