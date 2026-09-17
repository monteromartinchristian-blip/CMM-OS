"""Phase 11.5 — architecture and security gates for the conversation package.

``cmm.conversation`` is the conversational *boundary* of CMM OS, so every gate
here protects one property: the boundary adapts, it never becomes a second
owner and it never reaches past the application layer or the authorized
projection contracts.

* **no parallel authority** — the package defines no semantic equivalent of the
  design's frozen owner list (``ConversationStore``, ``ConversationRepository``,
  ``ConversationRuntime``, ``ConversationEngine``, ``ConversationRouter``,
  ``ConversationPlanner``, ``ConversationApprovalManager``,
  ``ConversationPermissionEngine``, ``ConversationMemoryStore``,
  ``ConversationKnowledgeStore``, ``ConversationProviderRegistry``,
  ``ConversationAgentRuntime``, ``ConversationWorkflowEngine``,
  ``ActiveRequestRegistry`` — spec section 24), compared case-insensitively and
  separator-insensitively, and no class of an owner shape at all: a class whose
  normalized name ends in ``store``, ``repository``, ``registry``, ``engine``,
  ``runtime``, ``planner`` or ``router`` is a parallel authority *by rule*
  (mirroring the owner-suffix rule of
  ``tests/application/test_architecture.py``), and the exact new-owner
  allowlist is empty;
* **no forbidden import** — ``cmm.memory``, ``cmm.cognitive``,
  ``cmm.agent_runtime``, ``kernel.llm`` and ``CMMChat`` (structural — no such
  Python package exists) are forbidden, ``cmm.api`` is *explicitly* forbidden
  (spec section 25: the conversation layer consumes the application boundary,
  never the transport adapter), and the internal-import allowlist is exact and
  frozen: ``cmm.application``, ``cmm.platform``, the canonical
  ``cmm.runtime.sessions`` store package, the Phase 10.45 projection contracts
  module ``cmm.domains.interface_integration_contracts`` and intra-package
  imports.  Every other ``cmm`` import — and every other ``cmm.domains.*``
  import (resolver, composer, permission, memory, internals) — fails the gate.
  The allowlist is additionally pinned *per module* with a liveness assertion,
  so a module that stops importing its allowed entry and a new unexplained
  import both fail loudly.  Import extraction is this gate's own and complete:
  ``import a.b`` and ``from a import b`` are both recorded as ``a.b``, so the
  ``from cmm import memory`` / ``from cmm import api`` evasions are caught
  (round-2 finding R2-1 on the shared ``_imported_modules`` helper), and that
  completeness is pinned by injecting every evasion form into a throwaway
  ``/tmp`` copy of the package;
* **dependency direction (reverse)** — ``cmm.runtime``, ``cmm.domains``,
  ``cmm.cognitive``, ``cmm.agent_runtime``, ``cmm.orchestration`` and
  ``kernel`` never import ``cmm.conversation`` or ``cmm.api``;
* **public serialization adversaries** — a recursive, structural walker over
  ``ConversationMessage.to_dict()`` and ``AssistantResponse.to_dict()`` output
  shows no secret-shaped or hidden-reasoning key and no forbidden fragment in
  any string value, and the deepest attacker-metadata payload the public
  recursion admits is rejected *at construction* (never silently sanitized),
  so it can never be persisted;
* **no hidden-reasoning surface** — no module of the package defines an
  attribute, field, function or argument named like chain-of-thought,
  scratchpad, private reasoning or hidden reasoning, and every
  ``reasoning_summary`` value is JSON-safe public data.

Every mutation pin runs against a throwaway ``/tmp`` copy of the package: the
real package is never modified, and a gate that survives its own violation is
a defect.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 23, 24, 25 and 26) and the committed Phase 11.5 plan (Task 9).
"""

from __future__ import annotations

import ast
import json
import math
import shutil
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from cmm.application.contracts import ApplicationResponse, ApplicationStatus
from cmm.conversation.contracts import (
    MAX_METADATA_DEPTH,
    AssistantResponse,
    ConversationAttachmentRef,
    ConversationCapabilityState,
    ConversationCapabilityStatus,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONVERSATION_PACKAGE = REPO_ROOT / "cmm" / "conversation"
CONVERSATION_PACKAGE_DOTTED = "cmm.conversation"

#: The frozen parallel-authority owner list of the design (spec section 24).
#: Each name is compared in its normalized form — lowercase with every
#: non-alphanumeric character removed — so ``ConversationStore``,
#: ``conversation_store`` and ``CONVERSATIONSTORE`` are one semantic form.
FORBIDDEN_PARALLEL_AUTHORITY_CLASSES = (
    "ConversationStore",
    "ConversationRepository",
    "ConversationRuntime",
    "ConversationEngine",
    "ConversationRouter",
    "ConversationPlanner",
    "ConversationApprovalManager",
    "ConversationPermissionEngine",
    "ConversationMemoryStore",
    "ConversationKnowledgeStore",
    "ConversationProviderRegistry",
    "ConversationAgentRuntime",
    "ConversationWorkflowEngine",
    "ActiveRequestRegistry",
)

#: The documented owner-suffix rule: any class defined inside the package whose
#: normalized name ends in one of these tokens is a parallel authority by rule,
#: because a store, repository, registry, engine, runtime, planner or router is
#: exactly the kind of owner the canonical lower layers own (spec section 24,
#: mirroring the owner-suffix rule of ``tests/application/test_architecture.py``
#: with this package's owner vocabulary).  A narrowly named helper or value
#: object is acceptable; an authority owner is not.
FORBIDDEN_OWNER_SUFFIX_TOKENS = (
    "Store",
    "Repository",
    "Registry",
    "Engine",
    "Runtime",
    "Planner",
    "Router",
)

#: The exact new-owner allowlist of ``cmm.conversation``: the boundary owns no
#: new authority at all.  Session authority stays with the canonical
#: ``SessionStore``; the package defines no request registry, no conversation
#: store and no routing owner.
ALLOWED_NEW_OWNER_CLASSES: frozenset[str] = frozenset()

#: Canonical packages the boundary must never name (spec sections 23 and 24).
#: ``CMMChat`` is structural: no such Python package is expected to exist, so
#: the check is on the import graph, not on the file system.
FORBIDDEN_CANONICAL_IMPORTS = (
    "cmm.memory",
    "cmm.cognitive",
    "cmm.agent_runtime",
    "kernel.llm",
    "CMMChat",
)

#: The HTTP adapter is never imported by the conversation package (controller
#: ruling 2 on Task 9, spec section 25): the conversation layer consumes the
#: application boundary, never the transport adapter.
FORBIDDEN_ADAPTER_IMPORT = "cmm.api"

#: Every *entry* the package may import, package-exact.  ``cmm.conversation``
#: is the intra-package entry; the other four are the sanctioned canonical
#: seams: the application boundary, the Phase 11.1 platform contracts, the
#: canonical shared-session store package and the Phase 10.45 projection
#: contracts.  A new import is a new seam and must be frozen here deliberately.
ALLOWED_INTERNAL_IMPORT_ENTRIES = (
    "cmm.conversation",
    "cmm.application",
    "cmm.platform",
    "cmm.runtime.sessions",
    "cmm.domains.interface_integration_contracts",
)

#: The frozen per-module liveness pin: which sanctioned entry each real module
#: imports.  Equality in both directions — a module that stops importing its
#: allowed entry, a module that acquires one, and a new module all fail loudly.
CONVERSATION_INTERNAL_IMPORTS_PIN: dict[str, frozenset[str]] = {
    "__init__.py": frozenset(),
    "capabilities.py": frozenset({"cmm.application"}),
    "contracts.py": frozenset(),
    "errors.py": frozenset(),
    "platform_module.py": frozenset({"cmm.platform"}),
    "projection.py": frozenset(
        {"cmm.application", "cmm.domains.interface_integration_contracts"}
    ),
    "service.py": frozenset(
        {
            "cmm.application",
            "cmm.domains.interface_integration_contracts",
            "cmm.runtime.sessions",
        }
    ),
    "state.py": frozenset({"cmm.runtime.sessions"}),
}

#: Layers the design places below (or beside) the conversational boundary.
#: None of them may import ``cmm.conversation`` or ``cmm.api`` (spec section 25).
REVERSE_DEPENDENCY_LAYERS = (
    "cmm.runtime",
    "cmm.domains",
    "cmm.cognitive",
    "cmm.agent_runtime",
    "cmm.orchestration",
    "kernel",
)

REVERSE_DEPENDENCY_FORBIDDEN_TARGETS = ("cmm.conversation", "cmm.api")

#: Keys and string-value fragments a public serialized payload must never carry
#: (spec section 23, the plan's Task 9 list).  Comparison is normalized exactly
#: like the contract layer screens keys: lowercase, separators removed, so
#: ``api_key``, ``apiKey``, ``Api-Key`` and ``x_api_key`` are one fragment.
FORBIDDEN_SERIALIZED_FRAGMENTS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
    "credential",
    "chain_of_thought",
    "scratchpad",
    "private_reasoning",
    "raw_prompt",
    "traceback",
)

#: Identifier forms that would name a hidden-reasoning surface (spec section
#: 23.1).  The scan is structural: it looks at identifiers the package
#: *defines* (classes, functions, fields, attributes, arguments), never at
#: string constants — the contract layer legitimately carries these spellings
#: as denylist values.
FORBIDDEN_HIDDEN_REASONING_FORMS = (
    "chain_of_thought",
    "scratchpad",
    "private_reasoning",
    "hidden_reasoning",
)

#: The secret-shaped key of the recursion-boundary adversary: it is placed at
#: the deepest mapping level the public grammar admits.
ATTACKER_METADATA_KEY = "api_key"

_TIMESTAMP = "2026-09-17T10:00:00+00:00"


# ── Structural helpers ───────────────────────────────────────────────────────


def _package_files(package: Path) -> list[Path]:
    return sorted(package.rglob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


def _classes_by_module(package: Path) -> dict[str, list[str]]:
    return {path.name: _defined_class_names(path) for path in _package_files(package)}


def _normalized_identifier(name: str) -> str:
    """Return the case- and separator-insensitive form of one identifier."""

    return "".join(character for character in name.lower() if character.isalnum())


def _matches_entry(module: str, entry: str) -> bool:
    """Return whether *module* is exactly *entry* or lives inside it."""

    return module == entry or module.startswith(f"{entry}.")


def _module_dotted_name(path: Path, package_dotted: str, package_dir: Path) -> str:
    """Return the dotted module name of one file inside its package."""

    parts = list(path.relative_to(package_dir).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return package_dotted
    return ".".join([package_dotted, *parts])


def _file_package(path: Path, package_dotted: str, package_dir: Path) -> str:
    """Return the package a file's relative imports resolve against."""

    module = _module_dotted_name(path, package_dotted, package_dir)
    if path.name == "__init__.py":
        return module
    return module.rpartition(".")[0]


def _imported_modules(
    path: Path, *, package_dotted: str, package_dir: Path
) -> set[str]:
    """Return every imported module of *path* as a dotted name.

    This extraction is this gate's own and complete: ``import a.b`` and
    ``from a import b`` are both recorded as ``a.b``, so importing a submodule
    through its parent package (``from cmm import memory``, ``from cmm import
    cognitive``, ``from cmm import api``) is visible — the shared
    ``_imported_modules`` helper of the closed-phase gates records only
    ``node.module`` for from-imports and misses exactly those evasions
    (round-2 finding R2-1 on Task 3).  Relative imports are resolved against
    the file's own package, so ``from .. import api`` inside the package is
    recorded as ``cmm.api`` too.
    """

    modules: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            base = _file_package(path, package_dotted, package_dir)
            for _ in range(node.level - 1):
                base = base.rpartition(".")[0]
            parent = f"{base}.{node.module}" if node.module else base
        else:
            if node.module is None:
                continue
            parent = node.module
        modules.update(f"{parent}.{alias.name}" for alias in node.names)
    return modules


def _imports_by_file(package: Path, package_dotted: str) -> dict[Path, set[str]]:
    return {
        path: _imported_modules(
            path, package_dotted=package_dotted, package_dir=package
        )
        for path in _package_files(package)
    }


def _internal_entries_used(path: Path) -> frozenset[str]:
    """Return the sanctioned internal entries one real package module imports."""

    modules = _imported_modules(
        path,
        package_dotted=CONVERSATION_PACKAGE_DOTTED,
        package_dir=CONVERSATION_PACKAGE,
    )
    return frozenset(
        entry
        for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
        if entry != CONVERSATION_PACKAGE_DOTTED
        and any(_matches_entry(module, entry) for module in modules)
    )


# ── Gate finders ─────────────────────────────────────────────────────────────


def find_named_authority_offenders(package: Path, owner: str) -> list[str]:
    """Report defined classes whose normalized name is exactly *owner*'s form."""

    normalized = _normalized_identifier(owner)
    return [
        f"{module}:{name}"
        for module, names in sorted(_classes_by_module(package).items())
        for name in names
        if _normalized_identifier(name) == normalized
    ]


def find_owner_shaped_classes(package: Path) -> set[str]:
    """Return every defined class whose normalized name ends in an owner token."""

    tokens = tuple(
        _normalized_identifier(token) for token in FORBIDDEN_OWNER_SUFFIX_TOKENS
    )
    return {
        name
        for names in _classes_by_module(package).values()
        for name in names
        if _normalized_identifier(name).endswith(tokens)
    }


def find_parallel_authority_offenders(package: Path) -> list[str]:
    """Report every parallel-authority violation of *package* (both rules)."""

    offenders = {
        f"{module}:{name}"
        for module, names in _classes_by_module(package).items()
        for name in names
        if name in find_owner_shaped_classes(package)
    }
    for owner in FORBIDDEN_PARALLEL_AUTHORITY_CLASSES:
        offenders.update(find_named_authority_offenders(package, owner))
    return sorted(offenders)


def find_internal_import_offenders(package: Path) -> list[str]:
    """Report every internal import outside the frozen allowlist.

    An internal import is any ``cmm`` import, including the bare ``cmm``
    package; every one must match the frozen entry list.  The domain rule is
    deliberately strict: only the Phase 10.45 projection contracts module is an
    allowed domain seam, so a resolver, composer, permission or internals
    import fails here as well.
    """

    offenders: list[str] = []
    for path, modules in sorted(
        _imports_by_file(package, CONVERSATION_PACKAGE_DOTTED).items()
    ):
        for module in sorted(modules):
            if module != "cmm" and not module.startswith("cmm."):
                continue
            if any(
                _matches_entry(module, entry)
                for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
            ):
                continue
            offenders.append(f"{path.name} -> {module}")
    return offenders


def find_forbidden_import_offenders(package: Path, target: str) -> list[str]:
    """Report every import of *target* (or of a module inside it)."""

    offenders: list[str] = []
    for path, modules in sorted(
        _imports_by_file(package, CONVERSATION_PACKAGE_DOTTED).items()
    ):
        for module in sorted(modules):
            if _matches_entry(module, target):
                offenders.append(f"{path.name} -> {module}")
    return offenders


def find_domain_bypass_offenders(package: Path) -> list[str]:
    """Report every domain import that is not the frozen projection contract."""

    allowed = "cmm.domains.interface_integration_contracts"
    offenders: list[str] = []
    for path, modules in sorted(
        _imports_by_file(package, CONVERSATION_PACKAGE_DOTTED).items()
    ):
        for module in sorted(modules):
            if module != "cmm.domains" and not module.startswith("cmm.domains."):
                continue
            if _matches_entry(module, allowed):
                continue
            offenders.append(f"{path.name} -> {module}")
    return offenders


def find_reverse_dependency_offenders(repo_root: Path, layer: str) -> list[str]:
    """Report imports of the boundary or the HTTP adapter inside *layer*."""

    offenders: list[str] = []
    for path, modules in sorted(_imports_by_file(repo_root / layer, layer).items()):
        for module in sorted(modules):
            for target in REVERSE_DEPENDENCY_FORBIDDEN_TARGETS:
                if _matches_entry(module, target):
                    offenders.append(f"{path.relative_to(repo_root)} -> {module}")
    return offenders


def _fragment_offenders(text: str, location: str) -> list[str]:
    normalized = _normalized_identifier(text)
    return [
        f"{location}: {fragment}"
        for fragment in FORBIDDEN_SERIALIZED_FRAGMENTS
        if _normalized_identifier(fragment) in normalized
    ]


def find_serialized_fragment_offenders(
    payload: object, location: str = "$"
) -> list[str]:
    """Walk *payload* recursively and report forbidden keys and string fragments.

    The walker is pure structure: every mapping key and every string value is
    compared in its normalized (lowercase, separator-free) form, so a
    secret-shaped key, a hidden-reasoning key and a forbidden fragment hidden
    anywhere in the recursion are all reported with their location.
    """

    offenders: list[str] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            where = f"{location}.{key}"
            if isinstance(key, str):
                offenders.extend(_fragment_offenders(key, where))
            else:
                offenders.append(f"{where}: non-string key {type(key).__name__}")
            offenders.extend(find_serialized_fragment_offenders(value, where))
        return offenders
    if isinstance(payload, Sequence) and not isinstance(
        payload, str | bytes | bytearray | memoryview
    ):
        for index, item in enumerate(payload):
            offenders.extend(
                find_serialized_fragment_offenders(item, f"{location}[{index}]")
            )
        return offenders
    if isinstance(payload, str):
        offenders.extend(_fragment_offenders(payload, location))
    return offenders


def find_non_json_safe_values(payload: object, location: str = "$") -> list[str]:
    """Walk *payload* recursively and report every value that is not JSON-native.

    Only ``None``, ``bool``, ``int``, finite ``float``, ``str``, mappings of
    those and sequences of those are public conversational data; everything
    else (an opaque object, binary data, a raw exception, a non-finite number,
    a non-string key) is reported.
    """

    offenders: list[str] = []
    if payload is None or isinstance(payload, bool | int | str):
        return offenders
    if isinstance(payload, float):
        if not math.isfinite(payload):
            offenders.append(f"{location}: non-finite float")
        return offenders
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if not isinstance(key, str):
                offenders.append(f"{location}: non-string key")
                continue
            offenders.extend(find_non_json_safe_values(value, f"{location}.{key}"))
        return offenders
    if isinstance(payload, Sequence) and not isinstance(
        payload, str | bytes | bytearray | memoryview
    ):
        for index, item in enumerate(payload):
            offenders.extend(find_non_json_safe_values(item, f"{location}[{index}]"))
        return offenders
    offenders.append(f"{location}: {type(payload).__name__}")
    return offenders


def _target_names(target: ast.expr) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, ast.Tuple | ast.List):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _defined_identifiers(path: Path) -> set[str]:
    """Return every identifier *path* defines, never a string constant."""

    identifiers: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            identifiers.add(node.name)
        elif isinstance(node, ast.AnnAssign):
            identifiers.update(_target_names(node.target))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                identifiers.update(_target_names(target))
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
    return identifiers


def find_hidden_reasoning_offenders(package: Path) -> list[str]:
    """Report every defined identifier that names a hidden-reasoning surface."""

    forms = tuple(
        _normalized_identifier(form) for form in FORBIDDEN_HIDDEN_REASONING_FORMS
    )
    return [
        f"{path.name}:{name}"
        for path in _package_files(package)
        for name in sorted(_defined_identifiers(path))
        if any(form in _normalized_identifier(name) for form in forms)
    ]


# ── Mutation-pin machinery: throwaway /tmp copies, never the real package ────


@contextmanager
def _mutable_package_copy(*probes: tuple[str, str]) -> Iterator[Path]:
    """Yield a throwaway ``/tmp`` copy of the package carrying the probe modules.

    The real package is never touched: the copy is created under ``/tmp``, the
    probe modules are written into it and the copy is removed afterwards, so a
    violation can be introduced and the gate exercised against it.
    """

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-pin-", dir="/tmp"))
    try:
        package = root / "cmm" / "conversation"
        shutil.copytree(
            CONVERSATION_PACKAGE,
            package,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        for name, source in probes:
            (package / name).write_text(source, encoding="utf-8")
        yield package
    finally:
        shutil.rmtree(root, ignore_errors=True)


@contextmanager
def _mutable_layer_copy(layer: str, source: str) -> Iterator[Path]:
    """Yield a throwaway ``/tmp`` repository root whose *layer* carries a probe."""

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-reverse-", dir="/tmp"))
    try:
        layer_dir = root / layer
        layer_dir.mkdir(parents=True)
        (layer_dir / "probe.py").write_text(source, encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _import_gate_offenders(package: Path) -> list[str]:
    """Return every offender of the import gates of the package."""

    offenders = find_internal_import_offenders(package)
    offenders.extend(find_domain_bypass_offenders(package))
    for target in (*FORBIDDEN_CANONICAL_IMPORTS, "kernel", FORBIDDEN_ADAPTER_IMPORT):
        offenders.extend(find_forbidden_import_offenders(package, target))
    return offenders


#: Evasion forms the complete import extraction must catch, each with the
#: canonical module it imports.  ``from cmm import memory`` style records the
#: submodule as ``cmm.memory`` exactly like ``import cmm.memory`` does; the
#: relative form ``from .. import api`` resolves to ``cmm.api`` of the parent
#: package (round-2 finding R2-1).
IMPORT_EVASION_FORMS: tuple[tuple[str, str], ...] = (
    ("from cmm import memory\n", "cmm.memory"),
    ("import cmm.memory\n", "cmm.memory"),
    ("from cmm.memory import TechnicalMemory\n", "cmm.memory"),
    ("from cmm import cognitive\n", "cmm.cognitive"),
    ("import cmm.cognitive\n", "cmm.cognitive"),
    ("from cmm import agent_runtime\n", "cmm.agent_runtime"),
    ("from cmm import api\n", "cmm.api"),
    ("from .. import api\n", "cmm.api"),
    ("import cmm.api\n", "cmm.api"),
    ("from kernel import llm\n", "kernel.llm"),
    ("import kernel.llm\n", "kernel.llm"),
    ("from CMMChat import runtime\n", "CMMChat"),
    ("from cmm import domains\n", "cmm.domains"),
    ("from cmm.domains import resolver\n", "cmm.domains.resolver"),
)

#: The sanctioned absolute spelling of the package's own modules: the gate must
#: admit it (a negative control against an over-broad import rule).
SANCTIONED_INTRA_PACKAGE_IMPORT = "from cmm import conversation\n"

#: Parallel-authority mutants: the exact semantic forms and the owner-suffix
#: rule, each injected into a ``/tmp`` copy of the package.
PARALLEL_AUTHORITY_MUTANTS: tuple[tuple[str, str, str], ...] = (
    ("mutant_store.py", "class ConversationStore:\n    pass\n", "ConversationStore"),
    ("mutant_engine.py", "class ConversationEngine:\n    pass\n", "ConversationEngine"),
    (
        "mutant_registry.py",
        "class ActiveRequestRegistry:\n    pass\n",
        "ActiveRequestRegistry",
    ),
    (
        "mutant_variant.py",
        "class conversation_repository:\n    pass\n",
        "conversation_repository",
    ),
    ("mutant_suffix.py", "class TranscriptStore:\n    pass\n", "TranscriptStore"),
    ("mutant_runtime.py", "class ChatRuntime:\n    pass\n", "ChatRuntime"),
)

#: Reverse-dependency mutants: a lower layer importing the boundary or the
#: adapter through an absolute or a parent-package spelling.
REVERSE_DEPENDENCY_MUTANTS: tuple[tuple[str, str, str], ...] = (
    ("cmm.runtime", "from cmm import conversation\n", "cmm.conversation"),
    ("cmm.domains", "import cmm.conversation\n", "cmm.conversation"),
    ("cmm.orchestration", "from cmm import api\n", "cmm.api"),
    ("kernel", "from cmm.conversation import service\n", "cmm.conversation"),
)

#: Hidden-reasoning-surface mutants: a dataclass field, an instance attribute
#: and a function argument naming a hidden-reasoning surface.
HIDDEN_REASONING_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_field.py",
        'class Draft:\n    chain_of_thought: str = ""\n',
        "chain_of_thought",
    ),
    (
        "mutant_attr.py",
        "class Draft:\n    def __init__(self) -> None:\n        self.scratchpad = []\n",
        "scratchpad",
    ),
    (
        "mutant_arg.py",
        "def draft(private_reasoning: str) -> str:\n    return private_reasoning\n",
        "private_reasoning",
    ),
)


def _import_evasion_ids() -> list[str]:
    return [
        f"{module.replace('.', '_')}-{index}"
        for index, (_, module) in enumerate(IMPORT_EVASION_FORMS)
    ]


def _mutant_ids(rows: Sequence[tuple[str, ...]]) -> list[str]:
    return [row[0].replace(".", "_").replace("/", "_") for row in rows]


# ── Public conversational builders ───────────────────────────────────────────


def _message(**overrides: object) -> ConversationMessage:
    fields: dict[str, object] = {
        "id": "msg-1",
        "session_id": "session-1",
        "role": ConversationRole.USER,
        "content": "A public question.",
        "created_at": _TIMESTAMP,
    }
    fields.update(overrides)
    return ConversationMessage(**fields)  # type: ignore[arg-type]


def _deepest_attacker_metadata(key: str) -> dict[str, object]:
    """Nest *key* at the deepest mapping level the public grammar admits."""

    payload: dict[str, object] = {key: "sk-attacker"}
    for level in range(MAX_METADATA_DEPTH - 1, 0, -1):
        payload = {f"level-{level}": payload}
    return payload


def _deepest_public_summary(levels: int) -> dict[str, Any]:
    """Return public reasoning-summary data nested to *levels* mappings."""

    value: object = "leaf"
    for _ in range(levels - 1):
        value = {"level": value}
    return {"summary": value}


def _populated_message() -> ConversationMessage:
    return _message(
        bot_id="bot-1",
        references=("source:1", "source:2"),
        attachments=(
            ConversationAttachmentRef(
                ref="attachment://document-1",
                kind="document",
                name="plan.md",
                media_type="text/markdown",
            ),
        ),
        lineage=ConversationLineage(supersedes_message_id="msg-0"),
        metadata={
            "thread": {"labels": ["plan", "review"], "priority": 2},
            "origin": "conversation",
        },
    )


def _populated_response() -> AssistantResponse:
    return AssistantResponse(
        message=_message(
            id="msg-2",
            role=ConversationRole.ASSISTANT,
            lineage=ConversationLineage(regenerates_message_id="msg-1"),
        ),
        sources=("source:1",),
        reasoning_summary={"result_refs": ["result:1"], "contradiction_refs": []},
        pending_questions=("question:1",),
        proposed_actions=("action:1",),
        approval_requests=("approval:1",),
        workflow_updates=("workflow:1",),
        domain_state={
            "primary_domain": "domain:health",
            "supporting_domains": ["domain:general"],
            "confidence": 0.9,
            "status": "ready",
        },
        capability_state=(
            ConversationCapabilityState(
                capability="response_streaming",
                requested=True,
                effective="response_event_stream",
                status=ConversationCapabilityStatus.DEGRADED,
            ),
        ),
        memory_updates=("memory:1",),
        warnings=("warning:1",),
    )


def _authorized_view() -> ConversationalDomainView:
    return ConversationalDomainView(
        primary_domain="domain:health",
        supporting_domains=("domain:general",),
        workflow_refs=("workflow:1",),
        question_refs=("question:1",),
        approval_refs=("approval:1",),
        source_refs=("source:1",),
        contradiction_refs=(),
        result_refs=("result:1",),
        memory_proposal_refs=("memory:1",),
        confidence=0.9,
        warning_refs=("warning:1",),
        status=DomainInterfaceStatus.READY,
    )


# ── 1. No parallel authority ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "owner", FORBIDDEN_PARALLEL_AUTHORITY_CLASSES, ids=lambda value: value.lower()
)
def test_conversation_package_defines_no_forbidden_parallel_authority_class(
    owner: str,
) -> None:
    offenders = find_named_authority_offenders(CONVERSATION_PACKAGE, owner)

    assert not offenders, (
        f"parallel authority defined in cmm.conversation: {sorted(offenders)}"
    )


def test_conversation_package_owner_shaped_classes_are_the_frozen_allowlist() -> None:
    """The boundary owns no class of an owner shape: the allowlist is empty.

    A class whose normalized name ends in ``store``, ``repository``,
    ``registry``, ``engine``, ``runtime``, ``planner`` or ``router`` is a
    parallel authority by rule; the exact allowlist is empty because every such
    owner stays with its canonical lower layer.
    """

    owner_shaped = find_owner_shaped_classes(CONVERSATION_PACKAGE)

    assert owner_shaped == set(ALLOWED_NEW_OWNER_CLASSES), (
        f"cmm.conversation may not introduce an owner: {sorted(owner_shaped)}"
    )


# ── 2. Forbidden imports and the frozen allowlist ────────────────────────────


@pytest.mark.parametrize(
    "forbidden",
    FORBIDDEN_CANONICAL_IMPORTS,
    ids=lambda value: value.replace(".", "_").lower(),
)
def test_conversation_package_imports_no_forbidden_canonical_package(
    forbidden: str,
) -> None:
    offenders = find_forbidden_import_offenders(CONVERSATION_PACKAGE, forbidden)

    assert not offenders, (
        f"cmm.conversation must not import {forbidden}: {sorted(offenders)}"
    )


def test_conversation_package_never_imports_the_http_adapter() -> None:
    """The boundary consumes the application layer, never the transport adapter.

    Controller ruling 2 on Task 9 and spec section 25: the conversation
    package may import ``cmm.application`` but must never import ``cmm.api``,
    directly or through a parent-package spelling.
    """

    offenders = find_forbidden_import_offenders(
        CONVERSATION_PACKAGE, FORBIDDEN_ADAPTER_IMPORT
    )

    assert not offenders, (
        "cmm.conversation must consume the application boundary, never the "
        f"HTTP adapter (spec section 25): {sorted(offenders)}"
    )


def test_conversation_package_imports_no_kernel_module() -> None:
    """The boundary reaches no kernel module at all (``kernel.llm`` included)."""

    offenders = find_forbidden_import_offenders(CONVERSATION_PACKAGE, "kernel")

    assert not offenders, (
        f"cmm.conversation must not import kernel: {sorted(offenders)}"
    )


def test_conversation_package_internal_imports_are_the_frozen_allowlist() -> None:
    offenders = find_internal_import_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        "cmm.conversation may import cmm.application, cmm.platform, "
        "cmm.runtime.sessions, cmm.domains.interface_integration_contracts and "
        f"its own modules only: {sorted(offenders)}"
    )


def test_conversation_package_imports_the_domain_projection_contract_only() -> None:
    """Domain imports are allowed only from the Phase 10.45 projection contracts."""

    offenders = find_domain_bypass_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        "the only sanctioned domain seam is "
        f"cmm.domains.interface_integration_contracts: {sorted(offenders)}"
    )


def test_the_internal_import_allowlist_is_live_and_pinned_per_module() -> None:
    """Every allowlist entry is live and every module's usage is frozen.

    The pin fails loudly in both directions: a module that stops importing its
    allowed entry (a stale allowlist) and a module that acquires a new entry or
    appears unexplained (a widened seam) are both a mismatch.
    """

    observed = {
        path.name: _internal_entries_used(path)
        for path in _package_files(CONVERSATION_PACKAGE)
    }

    assert observed == CONVERSATION_INTERNAL_IMPORTS_PIN, (
        f"the frozen per-module import pin no longer holds: {observed}"
    )

    live = set().union(*observed.values())
    sanctioned = set(ALLOWED_INTERNAL_IMPORT_ENTRIES) - {CONVERSATION_PACKAGE_DOTTED}

    assert live == sanctioned, (
        f"a frozen allowlist entry is stale or unexplained: {sorted(live)}"
    )


# ── 3. Dependency direction (reverse) ────────────────────────────────────────


@pytest.mark.parametrize(
    "layer", REVERSE_DEPENDENCY_LAYERS, ids=lambda value: value.replace(".", "_")
)
@pytest.mark.parametrize(
    "target",
    REVERSE_DEPENDENCY_FORBIDDEN_TARGETS,
    ids=lambda value: value.split(".")[1],
)
def test_lower_layers_do_not_import_the_boundary_or_the_adapter(
    layer: str, target: str
) -> None:
    offenders = [
        entry
        for entry in find_reverse_dependency_offenders(REPO_ROOT, layer)
        if _matches_entry(entry.split(" -> ", 1)[1], target)
    ]

    assert not offenders, f"{layer} must not import {target}: {sorted(offenders)}"


# ── 4. Public serialization adversaries ──────────────────────────────────────


def test_public_serialization_carries_no_forbidden_fragment() -> None:
    """The public payloads of both contracts are clean at every level."""

    for payload in (_populated_message().to_dict(), _populated_response().to_dict()):
        assert find_serialized_fragment_offenders(payload) == []
        assert find_non_json_safe_values(payload) == []
        assert (
            json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload
        )


def test_the_serialization_walker_detects_every_forbidden_fragment() -> None:
    """Sensitivity pin: the walker reports each fragment wherever it hides."""

    for fragment in FORBIDDEN_SERIALIZED_FRAGMENTS:
        hiding_places = (
            {fragment: "value"},
            {"outer": [{"inner": {fragment: "value"}}]},
            {f"x_{fragment}_y": "value"},
            {"note": f"prefix {fragment} suffix"},
        )
        for payload in hiding_places:
            offenders = find_serialized_fragment_offenders(payload)

            assert offenders, f"fragment not detected: {fragment!r} in {payload!r}"
            assert any(fragment in entry for entry in offenders)


def test_the_deepest_attacker_metadata_payload_is_rejected_at_construction() -> None:
    """The deepest admissible attacker payload fails closed at construction.

    The payload carries a secret-shaped key at the deepest mapping level the
    public recursion admits; the identical shape with a benign key is accepted,
    so the rejection is the key screen and not the recursion bound.  Because
    construction raises, no turn can carry the payload — it is never silently
    sanitized into a storable value.  The ``from_dict`` re-read rejects it the
    same way, so a persisted payload cannot be read back either.
    """

    attacker = _deepest_attacker_metadata(ATTACKER_METADATA_KEY)
    control = _deepest_attacker_metadata("note")

    assert _message(metadata=control).metadata

    with pytest.raises(ValueError):
        _message(metadata=attacker)

    serialized = _message(metadata=control).to_dict()
    serialized["metadata"] = attacker

    with pytest.raises(ValueError):
        ConversationMessage.from_dict(serialized)


# ── 5. No hidden-reasoning surface ───────────────────────────────────────────


def test_conversation_package_defines_no_hidden_reasoning_surface() -> None:
    """No module defines a chain-of-thought/scratchpad/private-reasoning name."""

    offenders = find_hidden_reasoning_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        f"a hidden-reasoning surface is defined in cmm.conversation: {offenders}"
    )


def test_the_projector_reasoning_summary_is_only_json_safe_public_data() -> None:
    """The real projector emits public, JSON-safe reasoning-summary data only."""

    response = ConversationResponseProjector().project(
        request_message=_message(),
        assistant_message_id="assistant-001",
        created_at=_TIMESTAMP,
        application_response=ApplicationResponse(
            request_id="request-1",
            api_version="v1",
            status=ApplicationStatus.SUCCESS,
            data={"echo": "ok"},
        ),
        domain_view=_authorized_view(),
        capability_state=(
            ConversationCapabilityState(
                capability="response_streaming",
                requested=True,
                effective="response_event_stream",
                status=ConversationCapabilityStatus.DEGRADED,
            ),
        ),
    )
    payload = response.to_dict()

    assert payload["reasoning_summary"] == {
        "result_refs": ["result:1"],
        "contradiction_refs": [],
    }
    assert find_serialized_fragment_offenders(payload) == []
    assert find_non_json_safe_values(payload) == []
    assert json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload


def test_deep_public_reasoning_summary_is_json_safe_public_data() -> None:
    """Even the deepest admissible public summary is JSON-native data only."""

    response = AssistantResponse(
        message=_message(),
        reasoning_summary=_deepest_public_summary(MAX_METADATA_DEPTH),
    )
    payload = response.to_dict()

    assert find_serialized_fragment_offenders(payload) == []
    assert find_non_json_safe_values(payload) == []
    assert json.loads(json.dumps(payload, sort_keys=True, allow_nan=False)) == payload


def test_the_public_value_checker_detects_non_json_safe_payloads() -> None:
    """Sensitivity pin: everything non-JSON-native is reported."""

    assert find_non_json_safe_values({"note": object()})
    assert find_non_json_safe_values({"note": b"bytes"})
    assert find_non_json_safe_values({"note": float("nan")})
    assert find_non_json_safe_values({"note": float("inf")})
    assert find_non_json_safe_values({"note": {1, 2}})
    assert find_non_json_safe_values({"note": ValueError("boom")})
    assert find_non_json_safe_values({1: "value"})
    assert find_non_json_safe_values({"note": [{"deep": object()}]})


# ── Mutation pins: every gate kills its own violation on a /tmp copy ─────────


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    PARALLEL_AUTHORITY_MUTANTS,
    ids=_mutant_ids(PARALLEL_AUTHORITY_MUTANTS),
)
def test_the_parallel_authority_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """The real violation injected into a /tmp copy makes the gate fail."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_parallel_authority_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders
        assert find_owner_shaped_classes(package) or find_named_authority_offenders(
            package, expected
        )


@pytest.mark.parametrize(
    ("source", "module"),
    IMPORT_EVASION_FORMS,
    ids=_import_evasion_ids(),
)
def test_the_import_gate_catches_every_evasion_form(source: str, module: str) -> None:
    """Every evasion form injected into a /tmp copy is reported by a gate."""

    with _mutable_package_copy(("probe.py", source)) as package:
        offenders = _import_gate_offenders(package)

        assert any(
            entry.split(" -> ", 1)[1] == module
            or entry.split(" -> ", 1)[1].startswith(f"{module}.")
            for entry in offenders
        ), f"evasion form not caught: {source!r}: {offenders}"


def test_the_import_gate_admits_the_sanctioned_intra_package_form() -> None:
    """The sanctioned absolute spelling imports the package's own modules only."""

    with _mutable_package_copy(("probe.py", SANCTIONED_INTRA_PACKAGE_IMPORT)) as (
        package
    ):
        offenders = _import_gate_offenders(package)

        assert not offenders, f"the gate over-blocks its own package: {offenders}"


@pytest.mark.parametrize(
    ("layer", "source", "module"),
    REVERSE_DEPENDENCY_MUTANTS,
    ids=_mutant_ids(REVERSE_DEPENDENCY_MUTANTS),
)
def test_the_reverse_dependency_gate_kills_its_own_violation(
    layer: str, source: str, module: str
) -> None:
    """A lower layer importing the boundary in a /tmp root makes the gate fail."""

    with _mutable_layer_copy(layer, source) as root:
        offenders = find_reverse_dependency_offenders(root, layer)

        assert any(
            entry.split(" -> ", 1)[1] == module
            or entry.split(" -> ", 1)[1].startswith(f"{module}.")
            for entry in offenders
        ), f"reverse dependency not caught: {source!r}: {offenders}"


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    HIDDEN_REASONING_MUTANTS,
    ids=_mutant_ids(HIDDEN_REASONING_MUTANTS),
)
def test_the_hidden_reasoning_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """A hidden-reasoning surface injected into a /tmp copy makes the gate fail."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_hidden_reasoning_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders
