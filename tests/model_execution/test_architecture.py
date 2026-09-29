"""CMMChat Wave E0 — executable architecture gates for the model execution seam.

These gates turn the E0 brief's prohibitions into executable assertions over the
real package:

* no parallel authority — no second orchestrator, provider registry, model
  router, model gateway, model catalog, provider abstraction, session owner,
  conversation store or usage owner is defined here;
* an exact, frozen module set and exact internal/external import allowlists, so
  the seam's dependencies can only grow deliberately;
* no bypass — the seam never imports the transport adapter (``cmm.api``) or the
  composition core (``cmm.platform``), never imports an HTTP/socket stack, never
  performs file I/O and never imports dynamically;
* no import-time side effect and no module-level singleton;
* no reverse dependency — no frozen layer imports ``cmm.model_execution``;
* exact reuse — every canonical LLM authority the seam names *is* the canonical
  object, not a copy;
* no credential-shaped literal anywhere in the package.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = REPO_ROOT / "cmm" / "model_execution"

#: The frozen E0 production module set of this package.
FROZEN_MODULES = frozenset(
    {
        "__init__.py",
        "canary.py",
        "composition.py",
        "contracts.py",
        "errors.py",
        "executor.py",
        "lanes.py",
        "turn.py",
    }
)

#: Canonical owners and authorities this package must never redefine.
FORBIDDEN_OWNER_CLASSES = (
    "ModelRouter",
    "ProviderRegistry",
    "ProviderFactory",
    "ModelCatalog",
    "ModelGateway",
    "RoutingPolicyEngine",
    "ProviderConnectionRegistry",
    "ProviderManifestRegistry",
    "ModelRouteCatalog",
    "LLMProvider",
    "OpenAICompatibleProvider",
    "OpenAICompatibleClient",
    "ConversationService",
    "ApplicationGateway",
    "RequestApplicationService",
    "Orchestrator",
    "SessionStore",
    "FileSessionStore",
    "EventBus",
    "ActiveRequestRegistry",
    "UsageStore",
    "WorkflowEngine",
    "AgentRuntime",
    "DomainResolver",
)

#: Owner-shaped suffixes: a class of this package ending in one of these would be
#: a new authority, transport, catalog or persistence seam.
FORBIDDEN_OWNER_SUFFIXES = (
    "Router",
    "Registry",
    "Catalog",
    "Gateway",
    "Store",
    "Repository",
    "Engine",
    "Runtime",
    "Manager",
    "Planner",
    "Bus",
    "Broker",
    "Pool",
    "Scheduler",
    "Client",
    "Adapter",
    "Provider",
    "Protocol",
)

#: The exact owner set E0 is allowed to define.
ALLOWED_OWNERS = frozenset(
    {
        "CanaryReport",
        "CanonicalModelExecutor",
        "ChatStreamFacts",
        "LocalModelExecution",
        "ModelExecutionError",
        "ModelExecutionErrorCode",
        "ModelExecutionFailure",
        "ModelExecutionParameters",
        "ModelExecutionRequest",
        "ModelExecutionResult",
        "ModelExecutionStatus",
        "ModelTurnRequest",
        "ModelTurnResult",
        "NormalizedModel",
        "ResolvedChatModel",
    }
)

#: Exact allowlist of internal roots the seam may import.
ALLOWED_INTERNAL_IMPORTS = (
    "cmm.application",
    "cmm.conversation",
    "cmm.model_execution",
    "cmm.orchestration",
    "kernel.llm",
)

#: Exact allowlist of standard-library roots the seam may import.
ALLOWED_EXTERNAL_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "argparse",
        "collections",
        "dataclasses",
        "datetime",
        "enum",
        "math",
        "os",
        "threading",
        "time",
        "types",
        "typing",
        "urllib",
        "uuid",
    }
)

#: Roots that would make the seam a transport, a network client or a storage
#: owner.  ``urllib.parse`` is the one permitted urllib member.
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "flask",
        "fastapi",
        "http",
        "httpx",
        "importlib",
        "io",
        "openai",
        "pathlib",
        "pickle",
        "requests",
        "shutil",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "ssl",
        "starlette",
        "subprocess",
        "tempfile",
        "urllib3",
        "uvicorn",
    }
)

#: Packages that must never import the seam, each anchored by a liveness check.
FROZEN_LAYER_ROOTS = (
    "cmm/agent_runtime",
    "cmm/api",
    "cmm/application",
    "cmm/cognitive",
    "cmm/conversation",
    "cmm/domains",
    "cmm/execution",
    "cmm/memory",
    "cmm/orchestration",
    "cmm/platform",
    "cmm/planner",
    "cmm/runtime",
    "cmm/validation",
    "cmm/workflows",
    "kernel",
)

#: Pure constructors that may legitimately run at module import time.
ALLOWED_IMPORT_TIME_CALLS = frozenset({"frozenset", "tuple", "list", "dict", "set"})

#: A credential-shaped literal: a bearer token or an API key committed by mistake.
_CREDENTIAL_LITERAL = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9_\-\.]{12,}|sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{12,})"
)


def _package_files() -> list[Path]:
    return sorted(PACKAGE.glob("*.py"))


def _sources() -> list[tuple[Path, str]]:
    return [(path, path.read_text(encoding="utf-8")) for path in _package_files()]


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


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


def _package_text() -> str:
    return "\n".join(source for _, source in _sources())


# ── 1. Frozen module set and owner vocabulary ────────────────────────────────


def test_the_package_contains_only_the_frozen_modules() -> None:
    present = {path.name for path in PACKAGE.iterdir() if path.is_file()}

    assert present == FROZEN_MODULES


def test_the_package_defines_exactly_the_allowed_owners() -> None:
    defined = {name for path in _package_files() for name in _defined_class_names(path)}

    assert defined == set(ALLOWED_OWNERS)


@pytest.mark.parametrize("owner", FORBIDDEN_OWNER_CLASSES)
def test_the_package_defines_no_parallel_canonical_owner(owner: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if name == owner or name.endswith(owner)
    ]

    assert not offenders, f"parallel canonical owner defined: {offenders}"


@pytest.mark.parametrize("suffix", FORBIDDEN_OWNER_SUFFIXES)
def test_the_package_defines_no_owner_shaped_class(suffix: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if name.endswith(suffix)
    ]

    assert not offenders, f"owner-shaped class defined: {offenders}"


def test_the_package_defines_no_provider_or_transport_protocol() -> None:
    """A new structural contract would be a parallel provider abstraction."""

    offenders = [
        f"{path.name}:{name}"
        for path in _package_files()
        for name in _defined_class_names(path)
        if name.endswith("Protocol") or name.startswith("_Discoverable")
    ]

    assert not offenders, f"parallel structural contract defined: {offenders}"


# ── 2. Import allowlists ─────────────────────────────────────────────────────


def test_the_package_imports_only_the_frozen_internal_roots() -> None:
    offenders: list[str] = []

    for path in _package_files():
        for module in _imported_modules(path):
            if not module.startswith("cmm."):
                continue
            if not any(
                module == entry or module.startswith(f"{entry}.")
                for entry in ALLOWED_INTERNAL_IMPORTS
            ):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"unexpected internal import: {sorted(offenders)}"


def test_the_package_never_imports_the_transport_or_composition_core() -> None:
    offenders: list[str] = []

    for path in _package_files():
        for module in _imported_modules(path):
            if module in {"cmm.api", "cmm.platform"} or module.startswith(
                ("cmm.api.", "cmm.platform.")
            ):
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"seam bypass import: {sorted(offenders)}"


def test_the_package_imports_only_the_frozen_external_roots() -> None:
    offenders: list[str] = []

    for path in _package_files():
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if module.startswith("cmm") or root == "kernel":
                continue
            if root not in ALLOWED_EXTERNAL_IMPORT_ROOTS:
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"unexpected external import: {sorted(offenders)}"


@pytest.mark.parametrize("root", sorted(FORBIDDEN_IMPORT_ROOTS))
def test_the_package_imports_no_transport_storage_or_dynamic_root(root: str) -> None:
    offenders = [
        f"{path.name} -> {module}"
        for path in _package_files()
        for module in _imported_modules(path)
        if module == root or module.startswith(f"{root}.")
    ]

    assert not offenders, f"forbidden import root {root}: {offenders}"


def test_the_package_imports_only_urllib_parse() -> None:
    offenders = [
        f"{path.name} -> {module}"
        for path in _package_files()
        for module in _imported_modules(path)
        if module.startswith("urllib") and module != "urllib.parse"
    ]

    assert not offenders, f"only urllib.parse is permitted: {offenders}"


def test_the_package_uses_no_dynamic_import_machinery() -> None:
    text = _package_text()

    for token in ("importlib", "__import__", "sys.modules", "eval(", "exec("):
        assert token not in text, f"dynamic machinery in the seam: {token}"


def test_the_package_performs_no_file_io() -> None:
    offenders: list[str] = []

    for path in _package_files():
        source = path.read_text(encoding="utf-8")
        for token in ("open(", "os.path", "Path(", "mkdir", "write_text", "read_text"):
            if token in source:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"file I/O in the seam: {offenders}"


# ── 3. No import-time side effect and no module-level singleton ──────────────


def test_no_module_level_statement_instantiates_an_owner() -> None:
    offenders: list[str] = []

    for path in _package_files():
        for statement in _parsed(path).body:
            if not isinstance(statement, ast.Assign | ast.AnnAssign):
                continue
            value = statement.value
            if value is None:
                continue
            for node in ast.walk(value):
                if isinstance(node, ast.Call):
                    name = getattr(node.func, "id", None) or getattr(
                        node.func, "attr", None
                    )
                    if name not in ALLOWED_IMPORT_TIME_CALLS:
                        offenders.append(f"{path.name}:{name}")

    assert not offenders, f"module-level instantiation: {offenders}"


def test_no_module_holds_a_service_singleton() -> None:
    text = _package_text()

    for token in ("_singleton", "_INSTANCE", "GLOBAL_", "global "):
        assert token not in text, f"module-level singleton in the seam: {token}"


# ── 4. Canonical reuse by identity ───────────────────────────────────────────


def test_the_package_reuses_the_canonical_llm_authorities_by_identity() -> None:
    from cmm.model_execution import composition, executor
    from kernel.llm.model_catalog import ModelCatalog
    from kernel.llm.model_router import ModelRouter
    from kernel.llm.provider import LLMProvider
    from kernel.llm.provider_factory import ProviderFactory
    from kernel.llm.provider_registry import ProviderRegistry

    assert composition.ModelRouter is ModelRouter
    assert composition.ProviderFactory is ProviderFactory
    assert composition.ProviderRegistry is ProviderRegistry
    assert composition.ModelCatalog is ModelCatalog
    assert executor.ModelRouter is ModelRouter
    assert executor.ProviderFactory is ProviderFactory
    assert executor.ProviderRegistry is ProviderRegistry
    assert executor.ModelCatalog is ModelCatalog
    assert executor.LLMProvider is LLMProvider


def test_the_package_reuses_the_canonical_conversation_and_decision_contracts() -> None:
    from cmm.conversation.service import ConversationService
    from cmm.model_execution import turn
    from cmm.orchestration.contracts import OrchestrationDecisionRecord
    from cmm.orchestration.decision_repository import OrchestrationDecisionRepository

    assert turn.ConversationService is ConversationService
    assert turn.OrchestrationDecisionRepository is OrchestrationDecisionRepository
    assert turn.OrchestrationDecisionRecord is OrchestrationDecisionRecord


def test_the_seam_delegates_rather_than_duplicating_routing_and_factory_work() -> None:
    """The executor calls the canonical collaborators instead of reimplementing."""

    source = (PACKAGE / "executor.py").read_text(encoding="utf-8")

    assert "self._model_router.decide(" in source
    assert "self._provider_factory.create_from_decision(" in source
    assert "provider.generate(" in source
    # No routing policy, ranking or provider construction lives here.
    for token in (
        "ModelRankingPolicy",
        "find_matching_models",
        "select_model",
        "OpenAICompatibleClient(",
        "ProviderSpec(",
        "ModelSpec(",
    ):
        assert token not in source, f"the seam duplicated canonical work: {token}"


# ── 5. Reverse dependencies ──────────────────────────────────────────────────


@pytest.mark.parametrize("layer", FROZEN_LAYER_ROOTS)
def test_no_frozen_layer_imports_the_model_execution_package(layer: str) -> None:
    root = REPO_ROOT.joinpath(*layer.split("/"))

    python_files = sorted(root.rglob("*.py"))
    assert python_files, f"liveness anchor missing for {layer}"

    offenders: list[str] = []
    for path in python_files:
        for module in _imported_modules(path):
            if module == "cmm.model_execution" or module.startswith(
                "cmm.model_execution."
            ):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, f"{layer} must not import the seam: {offenders}"


def test_the_seam_dependency_direction_is_one_way() -> None:
    """The seam consumes the decision and conversation contracts, never reverse."""

    offenders: list[str] = []

    for path in PACKAGE.glob("*.py"):
        for module in _imported_modules(path):
            if module.startswith(("cmm.model_execution",)):
                continue
            for forbidden in (
                "cmm.application.gateway",
                "cmm.orchestration.orchestrator",
            ):
                if module == forbidden:
                    offenders.append(
                        f"{path.name} imports {module} (the one gateway and the one "
                        "orchestrator are reached through the canonical public surface)"
                    )

    assert not offenders, f"seam bypass: {offenders}"


# ── 6. Secret hygiene ────────────────────────────────────────────────────────


def test_the_package_contains_no_credential_shaped_literal() -> None:
    for path, source in _sources():
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not _CREDENTIAL_LITERAL.search(node.value), (
                    f"credential-shaped literal in {path.name}"
                )


def test_the_package_reads_the_bearer_only_through_the_canonical_mechanism() -> None:
    source = (PACKAGE / "composition.py").read_text(encoding="utf-8")

    assert 'CHAT_ONLY_ROUTER_BEARER_ENV = "CMM_ROUTER_TOKEN"' in source
    assert "resolve_api_key()" in source
    for token in ("os.environ[", "getenv('Bearer", "Authorization"):
        assert token not in source, (
            f"credential read outside the canonical mechanism: {token}"
        )
