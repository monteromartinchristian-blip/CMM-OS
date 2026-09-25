"""Phase 11.50 — architecture and security gates for the client backend package.

``cmm.client_backend`` is a *facade* over the closed Phase 11.3 and Phase 11.5
owners, so every gate here protects one property: it adapts, delegates and
projects, and it never becomes a second authority.  Six families are screened:

* **no parallel authority** — the package defines no class whose name is an owner
  form (``Store``, ``Repository``, ``Registry``, ``Router``, ``Runtime``,
  ``Engine``, ``Resolver``, ``Manager``, ``Executor``, ``Planner``, ``Service``),
  and no named authority of the frozen design list.  The owner-suffix rule
  tolerates a trailing version marker, so ``ClientStoreV2`` is the same offender
  as ``ClientStore``;
* **no forbidden import** — ``kernel.llm``, ``cmm.orchestration.orchestrator``,
  ``cmm.api``, ``cmm.agent_runtime``, ``cmm.memory``, ``cmm.cognitive``,
  ``cmm.domains`` and ``CMMChat`` are forbidden, and the internal seam allowlist
  is exact and pinned per module.  The dependency direction is one way: the
  closed owners never import this package;
* **no dynamic dispatch or service locator** — no ``importlib``/``__import__``,
  no ``sys.modules`` access, no ``getattr(x, <computed>)`` dispatch, and no
  ``resolve_service`` / ``invoke`` / ``get_service`` surface.  The operation set
  is a closed enum, not a string routed to a method name;
* **no filesystem or network authority** — no ``open``, no ``pathlib`` read/write,
  no ``requests`` / ``httpx`` / ``urllib`` / ``aiohttp`` / ``socket``, so the
  facade cannot become a file store or an egress path;
* **no web framework and no CMMChat** — the facade is transport-neutral and no
  dependency points back toward a client application;
* **no hidden reasoning** — no attribute, field, argument or dynamic construction
  spells chain-of-thought, scratchpad or hidden reasoning.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_BACKEND_PACKAGE = REPO_ROOT / "cmm" / "client_backend"
CLIENT_BACKEND_DOTTED = "cmm.client_backend"

#: The frozen parallel-authority list of the Phase 11.50 design: every one of
#: these owners already exists (or is forbidden) elsewhere and must never be
#: re-created here.
FORBIDDEN_PARALLEL_AUTHORITY_CLASSES = (
    "ApplicationGateway",
    "ApplicationBackend",
    "BackendService",
    "ConversationService",
    "ClientBackendRuntime",
    "ClientBackendEngine",
    "ClientBackendRouter",
    "ClientBackendRegistry",
    "ClientBackendStore",
    "ClientBackendRepository",
    "ClientBackendResolver",
    "ClientBackendManager",
    "ClientBackendExecutor",
    "ClientStore",
    "ClientRepository",
    "SessionStore",
    "ConversationStore",
    "ModelGateway",
    "ProviderRegistry",
    "ModelCatalog",
    "Orchestrator",
    "ServiceLocator",
    "EventBus",
)

#: Any class defined inside the package whose version-stripped normalized name
#: ends in one of these tokens is a parallel authority *by rule*.
FORBIDDEN_OWNER_SUFFIX_TOKENS = (
    "Store",
    "Repository",
    "Registry",
    "Router",
    "Runtime",
    "Engine",
    "Resolver",
    "Manager",
    "Executor",
    "Planner",
    "Service",
    "Locator",
    "Bus",
)

VERSION_SUFFIX = re.compile(r"v?\d+$")

#: The exact new-owner allowlist: the facade owns no new authority at all.
ALLOWED_NEW_OWNER_CLASSES: frozenset[str] = frozenset()

#: Canonical packages and modules the facade must never import.
FORBIDDEN_CANONICAL_IMPORTS = (
    "cmm.agent_runtime",
    "cmm.api",
    "cmm.cognitive",
    "cmm.domains",
    "cmm.memory",
    "cmm.orchestration",
    "cmm.validation",
    "CMMChat",
    "kernel.llm",
)

#: Web frameworks, transports and UI toolkits that would make the facade a
#: transport owner.
FORBIDDEN_FRAMEWORK_IMPORT_ROOTS = (
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
    "requests",
    "socket",
    "starlette",
    "streamlit",
    "textual",
    "tkinter",
    "urllib",
    "uvicorn",
    "werkzeug",
)

#: The sanctioned internal seams, package-exact, pinned per module below.
ALLOWED_INTERNAL_IMPORT_ENTRIES = (
    "cmm.client_backend",
    "cmm.application.contracts",
    "cmm.application.errors",
    "cmm.application.gateway",
    "cmm.conversation.capabilities",
    "cmm.conversation.contracts",
    "cmm.conversation.errors",
    "cmm.conversation.service",
    "cmm.conversation.state",
    "cmm.platform.contracts",
    "cmm.platform.modules",
)

#: The frozen per-module liveness pin: which sanctioned entry each real module
#: imports.  Equality in both directions, so a module that stops importing its
#: allowed entry, a module that acquires one, and a new module all fail loudly.
CLIENT_BACKEND_INTERNAL_IMPORTS_PIN: dict[str, frozenset[str]] = {
    "__init__.py": frozenset({"cmm.application.contracts", "cmm.client_backend"}),
    "capabilities.py": frozenset(
        {
            "cmm.application.contracts",
            "cmm.client_backend",
            "cmm.conversation.capabilities",
            "cmm.conversation.contracts",
        }
    ),
    "contracts.py": frozenset({"cmm.application.contracts", "cmm.conversation.errors"}),
    "interface.py": frozenset(
        {
            "cmm.application.contracts",
            "cmm.application.errors",
            "cmm.application.gateway",
            "cmm.client_backend",
            "cmm.conversation.contracts",
            "cmm.conversation.errors",
            "cmm.conversation.service",
            "cmm.conversation.state",
        }
    ),
    "platform_module.py": frozenset(
        {"cmm.client_backend", "cmm.platform.contracts", "cmm.platform.modules"}
    ),
}

#: Layers the design places strictly below the facade.  None of them may import
#: ``cmm.client_backend``.
REVERSE_DEPENDENCY_LAYERS = (
    "cmm.application",
    "cmm.conversation",
    "cmm.platform",
    "cmm.orchestration",
    "kernel",
)

REVERSE_DEPENDENCY_FORBIDDEN_TARGET = "cmm.client_backend"

#: Dynamic-import machinery and runtime module-registry access: banned outright,
#: because a dynamic import cannot be screened statically.
DYNAMIC_IMPORT_CALL_FORMS = ("__import__", "import_module")

#: The service-locator surface the facade must never grow (design §42 and §43).
FORBIDDEN_LOCATOR_CALL_NAMES = (
    "resolve_any",
    "resolve_service",
    "get_service",
    "invoke",
)

#: Filesystem and network entrypoints the facade must never call (design §19).
#: ``Mapping.get`` is a mapping accessor, not an HTTP GET, so it is deliberately
#: absent; the network egress path is screened by the import gate above and by
#: the ``urllib``/``requests``/``httpx``/``aiohttp``/``socket`` call names here.
FORBIDDEN_FS_NETWORK_CALL_NAMES = (
    "open",
    "read_bytes",
    "read_text",
    "write_bytes",
    "write_text",
    "urlopen",
    "urlretrieve",
    "socket",
    "connect",
    "request",
    "post",
)

#: Identifier forms that would name a hidden-reasoning surface.
FORBIDDEN_HIDDEN_REASONING_FORMS = (
    "chain_of_thought",
    "chainofthought",
    "scratchpad",
    "private_reasoning",
    "hidden_reasoning",
)

#: The source-level fragments a client contract must never carry (design §25).
FORBIDDEN_SOURCE_FRAGMENTS = (
    "traceback",
    "stacktrace",
    "sk-live",
    "-----BEGIN",
    "system_prompt",
    "raw_prompt",
)


def _package_files(package: Path) -> list[Path]:
    return sorted(package.rglob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _relative_key(path: Path) -> str:
    return path.relative_to(CLIENT_BACKEND_PACKAGE).as_posix()


def _normalized_identifier(name: str) -> str:
    return "".join(character for character in name.lower() if character.isalnum())


def _unversioned_identifier(normalized: str) -> str:
    stripped = VERSION_SUFFIX.sub("", normalized)
    return stripped or normalized


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


def _classes_by_module() -> dict[str, list[str]]:
    return {
        _relative_key(path): _defined_class_names(path)
        for path in _package_files(CLIENT_BACKEND_PACKAGE)
    }


def _is_forbidden_owner_name(name: str) -> bool:
    normalized = _unversioned_identifier(_normalized_identifier(name))
    if not normalized:
        return False
    if normalized in {
        _normalized_identifier(owner) for owner in FORBIDDEN_PARALLEL_AUTHORITY_CLASSES
    }:
        return True
    return normalized.endswith(
        tuple(_normalized_identifier(token) for token in FORBIDDEN_OWNER_SUFFIX_TOKENS)
    )


def _module_dotted_name(path: Path) -> str:
    parts = list(path.relative_to(CLIENT_BACKEND_PACKAGE).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return CLIENT_BACKEND_DOTTED
    return ".".join([CLIENT_BACKEND_DOTTED, *parts])


def _file_package(path: Path) -> str:
    module = _module_dotted_name(path)
    if path.name == "__init__.py":
        return module
    return module.rpartition(".")[0]


def _imported_modules(path: Path) -> set[str]:
    """Return every imported module of *path* as a dotted name."""

    modules: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = _file_package(path)
            for _ in range(node.level - 1):
                base = base.rpartition(".")[0]
            parent = f"{base}.{node.module}" if node.module else base
        else:
            if node.module is None:
                continue
            parent = node.module
        modules.update(f"{parent}.{alias.name}" for alias in node.names)
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


def _matches_entry(module: str, entry: str) -> bool:
    return module == entry or module.startswith(f"{entry}.")


# ── No parallel authority ────────────────────────────────────────────────────


def test_the_package_defines_no_forbidden_parallel_authority() -> None:
    offenders = [
        f"{module}:{name}"
        for module, names in sorted(_classes_by_module().items())
        for name in names
        if _is_forbidden_owner_name(name)
    ]

    assert offenders == []


def test_the_new_owner_allowlist_is_empty() -> None:
    assert ALLOWED_NEW_OWNER_CLASSES == frozenset()


def test_the_owner_suffix_rule_is_load_bearing() -> None:
    """The rule really bites: a synthetic offender is detected."""

    assert _is_forbidden_owner_name("ClientStore")
    assert _is_forbidden_owner_name("ClientStoreV2")
    assert _is_forbidden_owner_name("client_backend_registry")
    assert _is_forbidden_owner_name("SessionRepository")
    assert not _is_forbidden_owner_name("ClientBackend")
    assert not _is_forbidden_owner_name("ClientOperation")


def test_the_package_defines_only_the_frozen_public_classes() -> None:
    """Every class the package defines is accounted for."""

    defined = {name for names in _classes_by_module().values() for name in names}
    assert defined == {
        "ClientBackend",
        "ClientBackendCapabilities",
        "ClientBackendCapabilityEvidence",
        "ClientBackendCapabilityStatus",
        "ClientBackendError",
        "ClientBackendErrorCode",
        "ClientBackendRequest",
        "ClientBackendResult",
        "ClientOperation",
    }


# ── No forbidden import ──────────────────────────────────────────────────────


@pytest.mark.parametrize("target", FORBIDDEN_CANONICAL_IMPORTS)
def test_the_package_imports_no_forbidden_canonical_module(target: str) -> None:
    offenders = [
        f"{_relative_key(path)} -> {module}"
        for path in _package_files(CLIENT_BACKEND_PACKAGE)
        for module in sorted(_imported_modules(path))
        if _matches_entry(module, target)
    ]

    assert offenders == []


@pytest.mark.parametrize("root", FORBIDDEN_FRAMEWORK_IMPORT_ROOTS)
def test_the_package_imports_no_transport_or_ui_framework(root: str) -> None:
    offenders = [
        f"{_relative_key(path)} -> {module}"
        for path in _package_files(CLIENT_BACKEND_PACKAGE)
        for module in sorted(_imported_modules(path))
        if module == root or module.startswith(f"{root}.")
    ]

    assert offenders == []


def test_every_internal_import_is_on_the_frozen_seam_allowlist() -> None:
    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        for module in sorted(_imported_modules(path)):
            if module != "cmm" and not module.startswith("cmm."):
                continue
            if any(
                _matches_entry(module, entry)
                for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
            ):
                continue
            offenders.append(f"{_relative_key(path)} -> {module}")

    assert offenders == []


def test_each_module_imports_exactly_its_pinned_seams() -> None:
    """The per-module liveness pin, in both directions."""

    assert set(CLIENT_BACKEND_INTERNAL_IMPORTS_PIN) == {
        _relative_key(path) for path in _package_files(CLIENT_BACKEND_PACKAGE)
    }

    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        key = _relative_key(path)
        modules = _imported_modules(path)
        used = frozenset(
            entry
            for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
            if entry != CLIENT_BACKEND_DOTTED
            and any(_matches_entry(module, entry) for module in modules)
        )
        if any(_matches_entry(module, CLIENT_BACKEND_DOTTED) for module in modules):
            used = used | {CLIENT_BACKEND_DOTTED}
        assert used == CLIENT_BACKEND_INTERNAL_IMPORTS_PIN[key], key


@pytest.mark.parametrize("layer", REVERSE_DEPENDENCY_LAYERS)
def test_the_closed_layers_never_import_the_client_backend(layer: str) -> None:
    """The dependency direction is one way: nothing below imports the facade."""

    directory = REPO_ROOT.joinpath(*layer.split("."))
    assert directory.is_dir(), f"the layer directory is missing: {directory}"
    files = sorted(directory.rglob("*.py"))
    assert files, f"the layer holds no Python file: {directory}"

    offenders: list[str] = []
    for path in files:
        for module in sorted(_imported_modules(path)):
            if _matches_entry(module, REVERSE_DEPENDENCY_FORBIDDEN_TARGET):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()} -> {module}"
                )

    assert offenders == []


# ── No dynamic dispatch or service locator ───────────────────────────────────


def test_the_package_uses_no_dynamic_import_machinery() -> None:
    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        key = _relative_key(path)
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.Call):
                callee = node.func
                name = (
                    callee.id
                    if isinstance(callee, ast.Name)
                    else callee.attr
                    if isinstance(callee, ast.Attribute)
                    else None
                )
                if name in DYNAMIC_IMPORT_CALL_FORMS:
                    offenders.append(f"{key}:{node.lineno}: {name}()")
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "modules"
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
            ):
                offenders.append(f"{key}:{node.lineno}: sys.modules")

    assert offenders == []


def test_the_package_exposes_no_service_locator_surface() -> None:
    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        for name in sorted(_called_names(path)):
            if name in FORBIDDEN_LOCATOR_CALL_NAMES:
                offenders.append(f"{_relative_key(path)}: {name}()")
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.FunctionDef) and node.name in (
                FORBIDDEN_LOCATOR_CALL_NAMES
            ):
                offenders.append(f"{_relative_key(path)}: def {node.name}()")

    assert offenders == []


def test_no_operation_is_routed_by_a_string_method_name() -> None:
    """The facade dispatches on enum identity, never on a caller-supplied name.

    ``getattr`` is allowed only as frozen-dataclass introspection over one of the
    facade's *own* declared fields; a computed or caller-supplied attribute name
    would be dynamic dispatch and fails closed here.
    """

    allowed_receivers = (
        "manifest",
        "self",
        "value",
        "value_type",
        "value_type.__dataclass_params__",
    )
    allowed_names = (
        "field_name",
        "_status_fields",
        "__dataclass_params__",
    )

    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        for node in ast.walk(_parsed(path)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "getattr":
                continue
            receiver = ast.unparse(node.args[0]) if node.args else ""
            attribute = ast.unparse(node.args[1]) if len(node.args) > 1 else ""
            if receiver in allowed_receivers or attribute in allowed_names:
                continue
            offenders.append(
                f"{_relative_key(path)}:{node.lineno}: getattr({receiver}, ...)"
            )

    assert offenders == []


# ── No filesystem or network authority ───────────────────────────────────────


def test_the_package_calls_no_filesystem_or_network_entrypoint() -> None:
    """The facade cannot become a file store, an egress path or a downloader."""

    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        for name in sorted(_called_names(path)):
            if name in FORBIDDEN_FS_NETWORK_CALL_NAMES:
                offenders.append(f"{_relative_key(path)}: {name}()")

    assert offenders == []


def test_the_package_does_not_import_pathlib() -> None:
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        modules = _imported_modules(path)
        assert "pathlib" not in modules, _relative_key(path)
        assert "os" not in modules, _relative_key(path)


# ── No hidden reasoning and no raw internal text ─────────────────────────────


def test_no_module_defines_a_hidden_reasoning_identifier() -> None:
    offenders: list[str] = []
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        key = _relative_key(path)
        identifiers: list[str] = []
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.ClassDef):
                identifiers.append(node.name)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                identifiers.append(node.name)
                identifiers.extend(argument.arg for argument in node.args.args)
                identifiers.extend(argument.arg for argument in node.args.kwonlyargs)
            elif isinstance(node, ast.Attribute):
                identifiers.append(node.attr)
        for identifier in identifiers:
            normalized = _normalized_identifier(identifier)
            for form in FORBIDDEN_HIDDEN_REASONING_FORMS:
                if _normalized_identifier(form) in normalized:
                    offenders.append(f"{key}: {identifier}")

    assert offenders == []


def test_no_public_constant_carries_raw_internal_text() -> None:
    """A public constant never names a traceback, a prompt or a credential."""

    from cmm.client_backend import CLIENT_BACKEND_ERROR_MESSAGES

    for code, message in CLIENT_BACKEND_ERROR_MESSAGES.items():
        lowered = message.lower()
        for fragment in FORBIDDEN_SOURCE_FRAGMENTS:
            assert fragment not in lowered, (code, fragment)


def test_the_package_contains_no_secret_shaped_literal() -> None:
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        source = path.read_text(encoding="utf-8")
        lowered = source.lower()
        for fragment in ("sk-live", "-----begin", "password=", "api_key="):
            assert fragment not in lowered, _relative_key(path)


# ── Documentation-facing invariants ──────────────────────────────────────────


def test_the_package_module_list_is_the_frozen_implementation_surface() -> None:
    assert {_relative_key(path) for path in _package_files(CLIENT_BACKEND_PACKAGE)} == {
        "__init__.py",
        "capabilities.py",
        "contracts.py",
        "interface.py",
        "platform_module.py",
    }


def test_the_package_has_no_subpackage() -> None:
    for path in CLIENT_BACKEND_PACKAGE.iterdir():
        if path.is_dir():
            assert path.name == "__pycache__", path


def test_the_non_cmm_dependency_set_is_standard_library_only() -> None:
    """The facade depends on the standard library and canonical cmm modules only."""

    standard_library_roots = {
        "__future__",
        "collections",
        "dataclasses",
        "enum",
        "math",
        "types",
        "typing",
    }

    union: set[str] = set()
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        union.update(_imported_modules(path))

    third_party = sorted(
        module
        for module in union
        if not module.startswith("cmm.")
        and module.split(".")[0] not in standard_library_roots
    )

    assert third_party == [], third_party
    assert isinstance(union, set)


def test_the_cmm_dependency_entry_set_is_frozen() -> None:
    """The union of canonical seams is exactly the frozen allowlist."""

    union: set[str] = set()
    for path in _package_files(CLIENT_BACKEND_PACKAGE):
        union.update(_imported_modules(path))

    canonical_entries = {
        entry
        for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
        if entry != CLIENT_BACKEND_DOTTED
        and any(_matches_entry(module, entry) for module in union)
    }

    assert canonical_entries == {
        "cmm.application.contracts",
        "cmm.application.errors",
        "cmm.application.gateway",
        "cmm.conversation.capabilities",
        "cmm.conversation.contracts",
        "cmm.conversation.errors",
        "cmm.conversation.service",
        "cmm.conversation.state",
        "cmm.platform.contracts",
        "cmm.platform.modules",
    }
