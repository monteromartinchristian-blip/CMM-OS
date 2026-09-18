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
  ``ActiveRequestRegistry`` — spec section 24), compared case-insensitively,
  separator-insensitively and version-suffix-insensitively (``ConversationStore``,
  ``conversation_store``, ``CONVERSATIONSTORE`` and ``ConversationStoreV2`` are
  one semantic form), and no class of an owner shape at all: a class whose
  normalized name ends in ``store``, ``repository``, ``registry``, ``engine``,
  ``runtime``, ``planner``, ``router`` or ``manager`` — with the same
  version-suffix tolerance, so ``ConversationApprovalManagerV2`` and
  ``ConversationPermissionEngine2`` are the family — is a parallel authority
  *by rule* (mirroring the owner-suffix rule of
  ``tests/application/test_architecture.py``), and the exact new-owner
  allowlist is empty.  The same vocabulary is screened where a name is
  *constructed* rather than declared: ``type("ConversationStore", ...)``,
  ``make_dataclass(...)``, an ``exec``/``eval`` code object, ``setattr`` with a
  string-constant attribute name and a module-level ``Name = ...`` alias that
  exports a forbidden name are all offenders, so a dynamic construction cannot
  hide an owner;
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
  import both fail loudly.  Import extraction is this gate's own and complete
  **for static import statements**: ``import a.b`` and ``from a import b`` are
  both recorded as ``a.b``, so the ``from cmm import memory`` /
  ``from cmm import api`` evasions are caught (round-2 finding R2-1 on the
  shared ``_imported_modules`` helper), and the ``import cmm as x; x.memory``
  and ``getattr(cmm, "memory")`` reaches are reported with the alias form that
  made them, never by the bare ``cmm`` fallback alone.  Extraction cannot see
  anything dynamic, so three further gates cover what it cannot: a structural
  rule fails ``importlib.import_module``, ``__import__`` and ``sys.modules[...]``
  inside the package outright, and one fresh-subprocess runtime check asserts
  that no forbidden module is bound into a package module's namespace, that no
  import executed by a package module resolves into a forbidden package, and
  that importing the package loads no forbidden module beyond the sanctioned
  seams' own closure — an allowed seam re-exporting a forbidden module is
  exactly what the binding lens catches.  The *blanket* form (no forbidden
  module anywhere in the subprocess delta) was measured and cannot hold: the
  Phase 10.45 seam's own package init eagerly imports the domain world
  (``cmm/domains/__init__.py`` pulls ``cmm.cognitive``, ``cmm.agent_runtime``
  and ``kernel.llm``), a pre-existing production fact outside this package, so
  the runtime check attributes that behavior instead of pretending it away.
  Every evasion form is pinned by injecting it into a throwaway copy of the
  package;
* **dependency direction (reverse)** — ``cmm.runtime``, ``cmm.domains``,
  ``cmm.cognitive``, ``cmm.agent_runtime``, ``cmm.orchestration`` and
  ``kernel`` never import ``cmm.conversation`` or ``cmm.api``.  Each layer is
  scanned at its REAL path, ``repo_root.joinpath(*layer.split("."))`` —
  ``<repo>/cmm/runtime``, never a directory literally named ``cmm.runtime`` —
  and each layer carries a liveness anchor: the directory must exist and hold
  at least one ``.py`` file, so a deleted, moved or empty layer fails loudly
  instead of reporting zero offenders forever (the Task 9 fix-round-1
  Critical);
* **public serialization adversaries** — a recursive, structural walker over
  ``ConversationMessage.to_dict()`` and ``AssistantResponse.to_dict()`` output
  shows no secret-shaped or hidden-reasoning key and no forbidden fragment in
  any string value; the fragment list is pinned to be a superset of the
  production key screen (``SECRET_LIKE_METADATA_KEYS`` and
  ``INTERNAL_DETAIL_METADATA_KEYS`` of ``cmm.conversation.contracts``, so a
  future production denial cannot silently escape the gate) with the gate-only
  entries documented as deliberate, and the deepest attacker-metadata payload
  the public recursion admits — ``MAX_METADATA_DEPTH`` nested mappings, the
  pinned recursion boundary where one more level fails the bound itself — is
  rejected *at construction*; the secret-shaped key is rejected at every
  admissible depth, so it can never be persisted;
* **no hidden-reasoning surface** — no module of the package defines an
  attribute, field, function or argument named like chain-of-thought,
  scratchpad, private reasoning or hidden reasoning, whether declared or built
  dynamically (``setattr``, ``make_dataclass``, ``type``, ``exec``), and every
  ``reasoning_summary`` value is JSON-safe public data.

Every mutation pin runs against a throwaway temp copy of the package (a
``tempfile.mkdtemp()`` sandbox, never the real package): the real package is
never modified, and a gate that survives its own violation is a defect.  The
reverse-dependency pins inject their violation in the REAL layout —
``<root>/cmm/runtime/probe.py``, never a directory named ``cmm.runtime`` —
because the wrong shape is what hid the fix-round-1 Critical.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 23, 24, 25 and 26) and the committed Phase 11.5 plan (Task 9).
"""

from __future__ import annotations

import ast
import functools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from cmm.application.contracts import ApplicationResponse, ApplicationStatus
from cmm.conversation.contracts import (
    INTERNAL_DETAIL_METADATA_KEYS,
    MAX_METADATA_DEPTH,
    SECRET_LIKE_METADATA_KEYS,
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
#: because a store, repository, registry, engine, runtime, planner, router or
#: manager is exactly the kind of owner the canonical lower layers own (spec
#: section 24, mirroring the owner-suffix rule of
#: ``tests/application/test_architecture.py`` with this package's owner
#: vocabulary).  The match tolerates a trailing version marker (``V2``, ``2``),
#: because ``ConversationPermissionManager`` and ``ConversationStoreV2`` are the
#: same owner family as their unsuffixed forms — the fix-round-1 evasion gap.
#: A narrowly named helper or value object is acceptable; an authority owner is
#: not.
FORBIDDEN_OWNER_SUFFIX_TOKENS = (
    "Store",
    "Repository",
    "Registry",
    "Engine",
    "Runtime",
    "Planner",
    "Router",
    "Manager",
)

#: A trailing version marker (``V2``, ``v2``, ``2``) is not a new identity:
#: owner vocabulary is compared with that suffix stripped, so
#: ``ConversationStoreV2`` is the frozen ``ConversationStore`` and
#: ``ConversationPermissionEngine2`` is the frozen
#: ``ConversationPermissionEngine``.  Only a trailing marker is stripped, so
#: ``ConversationDraft2`` still normalizes to a non-owner form.
VERSION_SUFFIX = re.compile(r"v?\d+$")

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

#: The forbidden module families the runtime import check screens: a forbidden
#: module must never be bound into, imported by or pulled through the package
#: (fix-round-1 transitive-import gap).
RUNTIME_FORBIDDEN_PREFIXES = (
    "cmm.memory",
    "cmm.cognitive",
    "cmm.agent_runtime",
    "kernel.llm",
)

#: The sanctioned seams imported before the runtime probe's recorded baseline,
#: so the check can attribute what the package *adds* on top of its own seams.
RUNTIME_SEAM_BASELINE = tuple(
    entry
    for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
    if entry != CONVERSATION_PACKAGE_DOTTED
)

#: Keys and string-value fragments a public serialized payload must never carry
#: (spec section 23, the plan's Task 9 list).  Comparison is normalized exactly
#: like the contract layer screens keys: lowercase, separators removed, so
#: ``api_key``, ``apiKey``, ``Api-Key`` and ``x_api_key`` are one fragment.
#: The list is pinned (``test_the_serialized_fragment_gate_covers_every_production_denial``)
#: to be a *superset* of the production key screen
#: ``SECRET_LIKE_METADATA_KEYS | INTERNAL_DETAIL_METADATA_KEYS`` of
#: ``cmm.conversation.contracts``, so a future production denial cannot
#: silently escape this walker; the entries production does not screen
#: (``private_reasoning``, ``raw_prompt``) are recorded in
#: ``GATE_ONLY_SERIALIZED_FRAGMENTS`` as deliberate.  Remediation MAJOR-03 moved
#: ``private_reasoning`` and ``raw_prompt`` into the production runtime screen,
#: so the gate now mirrors production exactly and no fragment is gate-only.
FORBIDDEN_SERIALIZED_FRAGMENTS = (
    # The production key screen of ``cmm.conversation.contracts``, mirrored:
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "passwd",
    "private_key",
    "secret",
    "token",
    # The production internal-detail screen, mirrored:
    "chain_of_thought",
    "hidden_reasoning",
    "scratchpad",
    "stack_trace",
    "traceback",
    "private_reasoning",
    "raw_prompt",
    "system_prompt",
    "prompt",
)

#: The deliberate gate-only fragments: the walker screens them, the production
#: key screen of ``cmm.conversation.contracts`` does not.  They are frozen so a
#: silent widening (or narrowing) of the gate is a test failure, not a
#: surprise.  Remediation MAJOR-03 emptied the list: the runtime now denies the
#: same vocabulary, and ``test_no_fragment_remains_gate_only_while_the_runtime_accepts_mappings``
#: keeps a future entry from silently re-opening a runtime gap.
GATE_ONLY_SERIALIZED_FRAGMENTS: tuple[str, ...] = ()

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


def _normalized_identifier(name: str) -> str:
    """Return the case- and separator-insensitive form of one identifier."""

    return "".join(character for character in name.lower() if character.isalnum())


def _unversioned_identifier(normalized: str) -> str:
    """Return *normalized* without a trailing version marker (``v2``, ``2``)."""

    stripped = VERSION_SUFFIX.sub("", normalized)
    return stripped or normalized


#: Normalized forms of the rule vocabulary, derived once from the frozen
#: constants so every screen (class statements, dynamic constructions, exported
#: aliases) compares the same forms.
FORBIDDEN_OWNER_TOKEN_FORMS = tuple(
    _normalized_identifier(token) for token in FORBIDDEN_OWNER_SUFFIX_TOKENS
)
FORBIDDEN_PARALLEL_AUTHORITY_FORMS = tuple(
    _normalized_identifier(owner) for owner in FORBIDDEN_PARALLEL_AUTHORITY_CLASSES
)
FORBIDDEN_HIDDEN_REASONING_FORMS_NORMALIZED = tuple(
    _normalized_identifier(form) for form in FORBIDDEN_HIDDEN_REASONING_FORMS
)

#: Import machinery that is banned outright inside the package (fix-round-1
#: evasion gap): a dynamic import cannot be screened statically, so the
#: mechanism itself is the offender.
DYNAMIC_IMPORT_CALL_FORMS = (
    "__import__",
    "import_module",
)


def _is_forbidden_owner_name(name: str) -> bool:
    """Return whether *name* is a forbidden owner form (both rules).

    Both rules are version-suffix tolerant: the named-authority rule compares
    the version-stripped normalized form for equality, and the owner-shape rule
    applies the documented suffix tokens to the version-stripped form.
    """

    normalized = _unversioned_identifier(_normalized_identifier(name))
    if not normalized:
        return False
    return normalized in FORBIDDEN_PARALLEL_AUTHORITY_FORMS or normalized.endswith(
        FORBIDDEN_OWNER_TOKEN_FORMS
    )


def _is_forbidden_hidden_reasoning_name(name: str) -> bool:
    """Return whether *name* spells a hidden-reasoning surface anywhere."""

    normalized = _normalized_identifier(name)
    return any(
        form in normalized for form in FORBIDDEN_HIDDEN_REASONING_FORMS_NORMALIZED
    )


def _is_forbidden_constructed_name(text: str) -> bool:
    """Return whether a constructed string-constant name is forbidden.

    A *constructed* name is screened as an owner form under both rules, as a
    hidden-reasoning form anywhere, and — because a construction has no
    namespace to protect — as any frozen owner name *inside* it, so
    ``type("MyConversationStore", ...)`` and
    ``setattr(Draft, "chain_of_thought", "")`` are both offenders.
    """

    if _is_forbidden_owner_name(text) or _is_forbidden_hidden_reasoning_name(text):
        return True
    normalized = _normalized_identifier(text)
    return any(owner in normalized for owner in FORBIDDEN_PARALLEL_AUTHORITY_FORMS)


def _relative_file_key(path: Path, package_root: Path) -> str:
    """Return a module's stable key: its path relative to the package root.

    Keying by ``path.name`` collides as soon as a future subpackage holds a
    file with the same basename, so every per-module dictionary and every
    offender string is keyed by the package-relative path instead.
    """

    return path.relative_to(package_root).as_posix()


def _classes_by_module(package: Path) -> dict[str, list[str]]:
    return {
        _relative_file_key(path, package): _defined_class_names(path)
        for path in _package_files(package)
    }


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
    """Report defined classes whose normalized name is *owner*'s semantic form.

    Version-suffix tolerant: ``ConversationStoreV2`` is the frozen
    ``ConversationStore`` written with a version marker, so it is the same
    parallel-authority identity (fix-round-1 evasion gap).
    """

    normalized = _normalized_identifier(owner)
    return [
        f"{module}:{name}"
        for module, names in sorted(_classes_by_module(package).items())
        for name in names
        if _unversioned_identifier(_normalized_identifier(name)) == normalized
    ]


def find_owner_shaped_classes(package: Path) -> set[str]:
    """Return every defined class whose name is an owner form by either rule.

    Version-suffix tolerant and with ``manager`` in the token list, so
    ``ConversationPermissionManager``, ``ConversationStoreV2``,
    ``ConversationApprovalManagerV2`` and ``ConversationPermissionEngine2`` are
    all owner-shaped by rule (fix-round-1 evasion gap).
    """

    return {
        name
        for names in _classes_by_module(package).values()
        for name in names
        if _is_forbidden_owner_name(name)
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


def _called_name(node: ast.expr) -> str | None:
    """Return the screened name a call's callee ends in.

    The final attribute name is matched, so a re-spelling through a module
    object (``builtins.type``, ``dataclasses.make_dataclass``) is still seen.
    """

    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _constant_strings(args: Sequence[ast.expr]) -> list[str]:
    """Return every string constant anywhere inside these argument expressions.

    The walk is recursive on purpose: a ``make_dataclass`` field name lives in a
    list of tuples (``[("chain_of_thought", str)]``), not in a direct argument,
    and it must be screened like a direct one.
    """

    strings: list[str] = []
    for argument in args:
        for node in ast.walk(argument):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                strings.append(node.value)
    return strings


def _construction_offenders(
    node: ast.Call, key: str, *, form: str, name_argument: ast.expr | None = None
) -> list[str]:
    """Screen one dynamic construction: its literal strings and its name.

    A name argument that is not a string constant cannot be screened at all,
    so it is an offender by rule: the boundary has no legitimate need to build
    a class or an attribute name dynamically.
    """

    offenders = [
        f"{key}:{node.lineno}: {form} constructs the forbidden name {text!r}"
        for text in _constant_strings(node.args)
        if _is_forbidden_constructed_name(text)
    ]
    if name_argument is not None and not (
        isinstance(name_argument, ast.Constant) and isinstance(name_argument.value, str)
    ):
        offenders.append(
            f"{key}:{node.lineno}: {form} constructs a name that is not a "
            "string constant (uninspectable)"
        )
    return offenders


def find_dynamic_identifier_offenders(package: Path) -> list[str]:
    """Report dynamic identifier construction inside *package*.

    A hidden-reasoning surface or a parallel owner can be built without a
    ``class`` statement, which the class-statement scan cannot see
    (fix-round-1 evasion gap).  Flagged forms, all screened against the frozen
    owner and hidden-reasoning vocabulary:

    * ``type("ConversationStore", (), {})`` — the three-argument construction
      form only; ``type(value).__name__`` is runtime introspection and is not a
      construction;
    * ``make_dataclass("ConversationStore", ...)`` and a hidden-reasoning field
      such as ``make_dataclass("Draft", [("chain_of_thought", str)])``;
    * ``setattr(obj, "chain_of_thought", ...)`` with a string-constant
      attribute name;
    * an ``exec``/``eval`` code object whose text spells a forbidden identifier.
    """

    offenders: list[str] = []
    for path in _package_files(package):
        key = _relative_file_key(path, package)
        for node in ast.walk(_parsed(path)):
            if not isinstance(node, ast.Call):
                continue
            called = _called_name(node.func)
            if called == "type" and len(node.args) >= 2:
                offenders.extend(
                    _construction_offenders(
                        node, key, form="type()", name_argument=node.args[0]
                    )
                )
            elif called == "make_dataclass":
                offenders.extend(
                    _construction_offenders(
                        node,
                        key,
                        form="make_dataclass()",
                        name_argument=node.args[0] if node.args else None,
                    )
                )
            elif called == "setattr" and len(node.args) >= 2:
                offenders.extend(
                    _construction_offenders(
                        node, key, form="setattr()", name_argument=node.args[1]
                    )
                )
            elif called in ("exec", "eval"):
                code_strings = _constant_strings(node.args)
                offenders.extend(
                    f"{key}:{node.lineno}: {called}() executes a code object "
                    f"spelling the forbidden name {text!r}"
                    for text in code_strings
                    if _is_forbidden_constructed_name(text)
                )
                if not code_strings:
                    offenders.append(
                        f"{key}:{node.lineno}: {called}() executes a code object "
                        "that is not a string constant (uninspectable)"
                    )
    return sorted(set(offenders))


def find_exported_alias_offenders(package: Path) -> list[str]:
    """Report module-level aliases that export a forbidden owner name.

    ``Registry = _InternalHelper`` exports an owner under a name no class
    statement carries, so the class-statement scan cannot see it
    (fix-round-1 evasion gap).  Only module-level assignments are screened:
    that is the namespace a name is *exported* from.
    """

    offenders: list[str] = []
    for path in _package_files(package):
        key = _relative_file_key(path, package)
        for node in _parsed(path).body:
            targets: list[ast.Name] = []
            if isinstance(node, ast.Assign):
                targets = [
                    target for target in node.targets if isinstance(target, ast.Name)
                ]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            offenders.extend(
                f"{key}:{node.lineno}: module-level alias {target.id} exports a "
                "forbidden owner name"
                for target in targets
                if _is_forbidden_owner_name(target.id)
            )
    return sorted(set(offenders))


def find_dynamic_import_offenders(package: Path) -> list[str]:
    """Report dynamic import machinery inside *package* (a mechanism ban).

    ``importlib.import_module("cmm.memory")``, ``__import__(...)`` and
    ``sys.modules[...]`` reach a forbidden module without an import statement,
    so static extraction cannot see the target (fix-round-1 evasion gap).  The
    boundary has no legitimate need for any of the three, so the mechanism
    itself is the offender.
    """

    offenders: list[str] = []
    for path in _package_files(package):
        key = _relative_file_key(path, package)
        for node in ast.walk(_parsed(path)):
            if isinstance(node, ast.Call):
                called = _called_name(node.func)
                if called == "__import__":
                    offenders.append(
                        f"{key}:{node.lineno}: dynamic import (__import__)"
                    )
                elif called == "import_module":
                    offenders.append(
                        f"{key}:{node.lineno}: dynamic import (importlib.import_module)"
                    )
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "modules"
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
            ):
                offenders.append(
                    f"{key}:{node.lineno}: runtime module registry access (sys.modules)"
                )
    return sorted(set(offenders))


def _cmm_root_bound_names(tree: ast.Module) -> set[str]:
    """Return every local name bound to the bare ``cmm`` package root."""

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import):
            continue
        for alias in node.names:
            if alias.name == "cmm":
                names.add(alias.asname or "cmm")
            elif alias.name.startswith("cmm.") and alias.asname is None:
                # ``import cmm.conversation`` binds the root package name too.
                names.add("cmm")
    return names


def _parent_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _attribute_chain(node: ast.Attribute) -> tuple[str, str] | None:
    """Return ``(root_name, dotted_suffix)`` for one attribute chain."""

    parts = [node.attr]
    current: ast.expr = node.value
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    return current.id, ".".join(reversed(parts))


def find_alias_attribute_offenders(package: Path) -> list[str]:
    """Report forbidden reaches through an alias of the bare ``cmm`` package.

    ``import cmm as x; x.memory`` and ``getattr(cmm, "memory")`` reach a
    forbidden package by attribute.  The bare ``cmm`` import already fails the
    allowlist, but the offender message must name the alias/attribute form that
    made the reach, so the signal is the reach itself and not the coincidence
    of the fallback (fix-round-1 evasion gap).
    """

    offenders: list[str] = []
    for path in _package_files(package):
        key = _relative_file_key(path, package)
        tree = _parsed(path)
        bound = _cmm_root_bound_names(tree)
        if not bound:
            continue
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                parent = parents.get(node)
                if isinstance(parent, ast.Attribute) and parent.value is node:
                    continue  # an inner segment of a longer chain
                chain = _attribute_chain(node)
                if chain is None or chain[0] not in bound:
                    continue
                resolved = f"cmm.{chain[1]}"
                if not any(
                    _matches_entry(resolved, entry)
                    for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
                ):
                    offenders.append(
                        f"{key}:{node.lineno}: alias attribute reach "
                        f"{chain[0]}.{chain[1]} -> {resolved}"
                    )
            elif isinstance(node, ast.Call) and _called_name(node.func) == "getattr":
                if len(node.args) < 2:
                    continue
                base = node.args[0]
                if not isinstance(base, ast.Name) or base.id not in bound:
                    continue
                name_argument = node.args[1]
                if isinstance(name_argument, ast.Constant) and isinstance(
                    name_argument.value, str
                ):
                    resolved = f"cmm.{name_argument.value}"
                    if not any(
                        _matches_entry(resolved, entry)
                        for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
                    ):
                        offenders.append(
                            f"{key}:{node.lineno}: getattr reach {base.id} with "
                            f"the attribute name {name_argument.value!r} -> "
                            f"{resolved}"
                        )
                else:
                    offenders.append(
                        f"{key}:{node.lineno}: getattr reach {base.id} with a "
                        "non-literal attribute name (uninspectable)"
                    )
    return sorted(set(offenders))


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
        key = _relative_file_key(path, package)
        for module in sorted(modules):
            if module != "cmm" and not module.startswith("cmm."):
                continue
            if any(
                _matches_entry(module, entry)
                for entry in ALLOWED_INTERNAL_IMPORT_ENTRIES
            ):
                continue
            offenders.append(f"{key} -> {module}")
    return offenders


def find_forbidden_import_offenders(package: Path, target: str) -> list[str]:
    """Report every import of *target* (or of a module inside it)."""

    offenders: list[str] = []
    for path, modules in sorted(
        _imports_by_file(package, CONVERSATION_PACKAGE_DOTTED).items()
    ):
        key = _relative_file_key(path, package)
        for module in sorted(modules):
            if _matches_entry(module, target):
                offenders.append(f"{key} -> {module}")
    return offenders


def find_domain_bypass_offenders(package: Path) -> list[str]:
    """Report every domain import that is not the frozen projection contract."""

    allowed = "cmm.domains.interface_integration_contracts"
    offenders: list[str] = []
    for path, modules in sorted(
        _imports_by_file(package, CONVERSATION_PACKAGE_DOTTED).items()
    ):
        key = _relative_file_key(path, package)
        for module in sorted(modules):
            if module != "cmm.domains" and not module.startswith("cmm.domains."):
                continue
            if _matches_entry(module, allowed):
                continue
            offenders.append(f"{key} -> {module}")
    return offenders


def _layer_directory(repo_root: Path, layer: str) -> Path:
    """Return the REAL directory of one dotted layer (``cmm.runtime`` → ``cmm/runtime``)."""

    return repo_root.joinpath(*layer.split("."))


def _scanned_layer_files(repo_root: Path, layer: str) -> list[Path]:
    """Return one layer's Python files, asserting the layer is really there.

    The liveness anchor of the reverse-dependency gate: *layer* is a DOTTED
    name, so the scanned directory is ``repo_root.joinpath(*layer.split("."))``
    — ``<root>/cmm/runtime``, never a directory literally named
    ``cmm.runtime``.  A deleted, moved or empty layer would make every
    reverse-dependency check scan nothing and pass forever (the exact shape
    that hid the fix-round-1 Critical, where five of six layers were never
    scanned), so the anchor fails loudly instead.
    """

    directory = _layer_directory(repo_root, layer)
    assert directory.is_dir(), (
        f"the reverse-dependency layer directory is missing: {directory} — "
        "the gate would silently scan nothing"
    )
    files = _package_files(directory)
    assert files, (
        f"the reverse-dependency layer directory holds no Python file: "
        f"{directory} — the gate would silently scan nothing"
    )
    return files


@functools.cache
def find_reverse_dependency_offenders(repo_root: Path, layer: str) -> tuple[str, ...]:
    """Report imports of the boundary or the HTTP adapter inside *layer*.

    The layer is scanned at its real path (see ``_scanned_layer_files``) and
    the result is cached per (root, layer): the real layers hold hundreds of
    files and twelve parametrized runs must not re-parse them.  Callers must
    not mutate the returned tuple.
    """

    directory = _layer_directory(repo_root, layer)
    files = _scanned_layer_files(repo_root, layer)
    offenders: list[str] = []
    for path in files:
        for module in sorted(
            _imported_modules(path, package_dotted=layer, package_dir=directory)
        ):
            for target in REVERSE_DEPENDENCY_FORBIDDEN_TARGETS:
                if _matches_entry(module, target):
                    offenders.append(
                        f"{path.relative_to(repo_root).as_posix()} -> {module}"
                    )
    return tuple(sorted(set(offenders)))


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


def production_denied_fragments() -> tuple[str, ...]:
    """Return the production key screen of ``cmm.conversation.contracts``."""

    return tuple(sorted(SECRET_LIKE_METADATA_KEYS | INTERNAL_DETAIL_METADATA_KEYS))


def find_fragment_gate_drift(
    production_denials: Sequence[str], gate_fragments: Sequence[str]
) -> list[str]:
    """Return every production denial the serialization gate does not screen.

    The relationship is pinned, never assumed: the gate's normalized fragment
    set must be a superset of the production key screen, so a future
    production denial cannot silently escape the walker (fix-round-1 gap: the
    duplicated list had drifted in both directions).
    """

    gate = {_normalized_identifier(fragment) for fragment in gate_fragments}
    return sorted(
        {
            fragment
            for fragment in production_denials
            if _normalized_identifier(fragment) not in gate
        }
    )


def find_undeclared_gate_fragments(
    gate_fragments: Sequence[str],
    production_denials: Sequence[str],
    declared_gate_only: Sequence[str],
) -> list[str]:
    """Return every gate fragment neither production nor the frozen list names.

    The other direction of the same pin: the gate may screen *more* than
    production only through the entries documented as deliberate in
    ``GATE_ONLY_SERIALIZED_FRAGMENTS``; a silent widening is a gate defect too.
    """

    production = {_normalized_identifier(fragment) for fragment in production_denials}
    declared = {_normalized_identifier(fragment) for fragment in declared_gate_only}
    return sorted(
        {
            fragment
            for fragment in gate_fragments
            if _normalized_identifier(fragment) not in production
            and _normalized_identifier(fragment) not in declared
        }
    )


#: The fresh-subprocess runtime probe of the import closure (fix-round-1
#: transitive-import gap).  It records the module set after the sanctioned
#: seams are imported, imports the target modules through a recording
#: ``builtins.__import__``, and reports three attribution lenses:
#:
#: * ``binding_offenders`` — a module, class, function or instance *bound into*
#:   a target module's namespace that is, or is defined in, a forbidden module.
#:   This is the lens that catches an allowed seam re-exporting a forbidden
#:   module, and an ``importlib.import_module(...)`` whose result is bound;
#: * ``import_offenders`` — an import statement *executed by* a target module
#:   that resolves into a forbidden module (``from cmm import memory``,
#:   ``import cmm.memory``, ``__import__("cmm.memory")``);
#: * ``closure_offenders`` — a forbidden module the target imports load *beyond
#:   the sanctioned seams' own closure* (an import whose result is discarded is
#:   still visible here whenever the module is outside that closure).
#:
#: The blanket form — "no forbidden module anywhere in the subprocess delta" —
#: was measured and cannot hold on this repository: importing the one
#: sanctioned Phase 10.45 seam executes ``cmm/domains/__init__.py``, which
#: eagerly imports the domain world (``cmm.cognitive``, ``cmm.agent_runtime``,
#: ``kernel.llm``), pre-existing production behavior outside
#: ``cmm.conversation``.  Attribution is the honest form of the same check.
_RUNTIME_PROBE = r"""
import builtins, json, sys, types

forbidden_prefixes, baseline_modules, target_modules = (
    json.loads(sys.argv[1]), json.loads(sys.argv[2]), json.loads(sys.argv[3])
)


def offshore(name):
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in forbidden_prefixes
    )


for name in baseline_modules:
    __import__(name)
pre = set(sys.modules)

records = []
original_import = builtins.__import__


def recording_import(name, globals=None, locals=None, fromlist=(), level=0):
    frame = sys._getframe(1)
    records.append(
        (frame.f_globals.get("__name__", ""), name, level, list(fromlist or ()))
    )
    return original_import(name, globals, locals, fromlist, level)


builtins.__import__ = recording_import
try:
    for name in target_modules:
        __import__(name, fromlist=("*",))
finally:
    builtins.__import__ = original_import
post = set(sys.modules)


def resolve(caller, name, level, fromlist):
    if not level:
        parent = name
    else:
        base = caller.rpartition(".")[0]
        for _ in range(level - 1):
            base = base.rpartition(".")[0]
        parent = f"{base}.{name}" if name else base
    return [parent, *(f"{parent}.{item}" for item in fromlist)]


import_offenders = set()
for caller, name, level, fromlist in records:
    if caller != "cmm.conversation" and not caller.startswith("cmm.conversation."):
        continue
    for resolved in resolve(caller, name, level, fromlist):
        if offshore(resolved):
            import_offenders.add(f"{caller} -> {resolved}")

binding_offenders = set()
for name in target_modules:
    module = sys.modules.get(name)
    if module is None:
        continue
    for attribute, value in vars(module).items():
        if isinstance(value, types.ModuleType):
            if offshore(getattr(value, "__name__", "")):
                binding_offenders.add(f"{name}.{attribute} -> {value.__name__}")
        else:
            owner = getattr(value, "__module__", None)
            if isinstance(owner, str) and offshore(owner):
                binding_offenders.add(f"{name}.{attribute} is defined in {owner}")

closure_offenders = sorted(name for name in post - pre if offshore(name))

print(json.dumps({
    "import_offenders": sorted(import_offenders),
    "binding_offenders": sorted(binding_offenders),
    "closure_offenders": closure_offenders,
}))
"""


def find_runtime_import_offenders(
    module_names: Sequence[str], *, root: Path, baseline_modules: Sequence[str] = ()
) -> tuple[list[str], list[str], list[str]]:
    """Run the runtime probe in a fresh subprocess; return its three lenses.

    Returns ``(import_offenders, binding_offenders, closure_offenders)`` as
    reported by ``_RUNTIME_PROBE``.  The subprocess is rooted at *root* (its
    modules resolve from there, with ``PYTHONPATH`` pinned to the same root), so
    the check can be exercised against a throwaway copy exactly like every
    other pin.  A probe that fails to run is an error, never an empty result.
    """

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _RUNTIME_PROBE,
            json.dumps(list(RUNTIME_FORBIDDEN_PREFIXES)),
            json.dumps(list(baseline_modules)),
            json.dumps(list(module_names)),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    assert completed.returncode == 0, (
        f"the runtime import probe failed to run: {completed.stderr[-2000:]}"
    )
    report = json.loads(completed.stdout)
    return (
        list(report["import_offenders"]),
        list(report["binding_offenders"]),
        list(report["closure_offenders"]),
    )


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

    return [
        f"{_relative_file_key(path, package)}:{name}"
        for path in _package_files(package)
        for name in sorted(_defined_identifiers(path))
        if _is_forbidden_hidden_reasoning_name(name)
    ]


# ── Mutation-pin machinery: throwaway temp copies, never the real package ────


@contextmanager
def _mutable_package_copy(*probes: tuple[str, str]) -> Iterator[Path]:
    """Yield a throwaway temp copy of the package carrying the probe modules.

    The real package is never touched: the copy is created under the system
    temp directory (``tempfile.mkdtemp()`` defaults), the probe modules are
    written into it and the copy is removed afterwards, so a violation can be
    introduced and the gate exercised against it.
    """

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-pin-"))
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
    """Yield a throwaway repository root whose *layer* carries a probe.

    The layer directory is created in the REAL layout —
    ``root.joinpath(*layer.split("."))``, so ``cmm.runtime`` becomes
    ``<root>/cmm/runtime`` — because a directory literally named
    ``cmm.runtime`` is not a shape this repository can take and is exactly what
    hid the fix-round-1 Critical.
    """

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-reverse-"))
    try:
        layer_dir = _layer_directory(root, layer)
        layer_dir.mkdir(parents=True)
        (layer_dir / "probe.py").write_text(source, encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@contextmanager
def _mutable_runtime_copy(*probes: tuple[str, str]) -> Iterator[Path]:
    """Yield a minimal throwaway repository root for the runtime probe.

    The root carries the real layout (``cmm/conversation/probe.py``) plus
    importable stubs of the forbidden families, so the runtime check can be
    pointed at a violation the way every other gate is.
    """

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-runtime-"))
    try:
        (root / "cmm" / "conversation").mkdir(parents=True)
        (root / "cmm" / "__init__.py").write_text("", encoding="utf-8")
        (root / "cmm" / "conversation" / "__init__.py").write_text("", encoding="utf-8")
        (root / "cmm" / "memory").mkdir()
        (root / "cmm" / "memory" / "__init__.py").write_text(
            "class TechnicalMemory:\n    pass\n", encoding="utf-8"
        )
        (root / "kernel" / "llm").mkdir(parents=True)
        (root / "kernel" / "__init__.py").write_text("", encoding="utf-8")
        (root / "kernel" / "llm" / "__init__.py").write_text("", encoding="utf-8")
        for name, source in probes:
            (root / name).write_text(source, encoding="utf-8")
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _import_gate_offenders(package: Path) -> list[str]:
    """Return every offender of the import gates of the package.

    De-duplicated: one import can be an offender of more than one rule (a
    ``kernel.llm`` import is both off the internal allowlist and a forbidden
    target), and the same offender string must not be reported twice.
    """

    offenders = find_internal_import_offenders(package)
    offenders.extend(find_domain_bypass_offenders(package))
    for target in (*FORBIDDEN_CANONICAL_IMPORTS, "kernel", FORBIDDEN_ADAPTER_IMPORT):
        offenders.extend(find_forbidden_import_offenders(package, target))
    offenders.extend(find_dynamic_import_offenders(package))
    offenders.extend(find_alias_attribute_offenders(package))
    return sorted(set(offenders))


#: Evasion forms the complete import extraction must catch, each with the
#: canonical module it imports.  ``from cmm import memory`` style records the
#: submodule as ``cmm.memory`` exactly like ``import cmm.memory`` does; the
#: relative form ``from .. import api`` resolves to ``cmm.api`` of the parent
#: package (round-2 finding R2-1); the alias and attribute forms reach the same
#: module through a bound name and must be reported with that form
#: (fix-round-1 evasion gap).
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
    ("import cmm as alias\n\nalias.memory\n", "cmm.memory"),
    ('import cmm\n\ngetattr(cmm, "memory")\n', "cmm.memory"),
)

#: The sanctioned absolute spelling of the package's own modules: the gate must
#: admit it (a negative control against an over-broad import rule).
SANCTIONED_INTRA_PACKAGE_IMPORT = "from cmm import conversation\n"

#: Parallel-authority mutants: the exact semantic forms and the owner-suffix
#: rule, each injected into a temp copy of the package.
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

#: Owner-family mutants (fix-round-1 gap): the two seams the pre-fix rule left
#: open — a new ``manager`` owner suffix and a trailing version marker on a
#: frozen owner identity.
OWNER_FAMILY_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_permission_manager.py",
        "class ConversationPermissionManager:\n    pass\n",
        "ConversationPermissionManager",
    ),
    (
        "mutant_store_v2.py",
        "class ConversationStoreV2:\n    pass\n",
        "ConversationStoreV2",
    ),
    (
        "mutant_approval_manager_v2.py",
        "class ConversationApprovalManagerV2:\n    pass\n",
        "ConversationApprovalManagerV2",
    ),
    (
        "mutant_permission_engine_2.py",
        "class ConversationPermissionEngine2:\n    pass\n",
        "ConversationPermissionEngine2",
    ),
)

#: The legitimate control the owner-family rule must admit: a narrowly named
#: value object and a version-suffixed *non-owner* name must stay unflagged.
OWNER_FAMILY_CONTROL: tuple[str, str] = (
    "control_owner_family.py",
    (
        "class ConversationDraftNote:\n    pass\n\n\nclass ConversationDigest2:\n"
        "    pass\n"
    ),
)

#: Reverse-dependency mutants: every ``cmm`` layer the design places below the
#: boundary plus ``kernel``, each importing the boundary or the adapter through
#: a different real spelling — absolute, parent-package and relative.  The
#: probe is injected in the REAL layout (``<root>/cmm/runtime/probe.py``), the
#: shape the pre-fix pin did not use and the gate did not scan (fix-round-1
#: Critical).
REVERSE_DEPENDENCY_MUTANTS: tuple[tuple[str, str, str], ...] = (
    ("cmm.runtime", "from cmm import conversation\n", "cmm.conversation"),
    ("cmm.domains", "import cmm.conversation\n", "cmm.conversation"),
    ("cmm.cognitive", "from .. import api\n", "cmm.api"),
    ("cmm.agent_runtime", "from cmm import api\n", "cmm.api"),
    ("cmm.orchestration", "from cmm.conversation import service\n", "cmm.conversation"),
    ("kernel", "import cmm.api\n", "cmm.api"),
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

#: Dynamic-identifier-construction mutants (fix-round-1 gap): the same owner
#: and hidden-reasoning vocabulary reached without a ``class`` statement.
DYNAMIC_IDENTIFIER_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_dynamic_type.py",
        '_InternalHelper = type("ConversationStore", (), {})\n',
        "ConversationStore",
    ),
    (
        "mutant_dynamic_dataclass.py",
        (
            "from dataclasses import make_dataclass\n\n"
            '_Created = make_dataclass("ConversationApprovalManager", [])\n'
        ),
        "ConversationApprovalManager",
    ),
    (
        "mutant_dynamic_dataclass_field.py",
        (
            "from dataclasses import make_dataclass\n\n"
            '_Draft = make_dataclass("Draft", [("chain_of_thought", str)])\n'
        ),
        "chain_of_thought",
    ),
    (
        "mutant_dynamic_setattr.py",
        'class _Draft:\n    pass\n\n\nsetattr(_Draft, "scratchpad", "")\n',
        "scratchpad",
    ),
    (
        "mutant_dynamic_exec.py",
        'exec("class ConversationStore:\\n    pass\\n")\n',
        "ConversationStore",
    ),
    (
        "mutant_dynamic_opaque.py",
        "_helper = object()\n_Created = type(_helper, (), {})\n",
        "uninspectable",
    ),
)

#: Exported-alias mutants (fix-round-1 gap): a module-level name that no class
#: statement carries, exporting an owner identity.
EXPORTED_ALIAS_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_alias_registry.py",
        "_InternalHelper = object()\n\nRegistry = _InternalHelper\n",
        "Registry",
    ),
    (
        "mutant_alias_store_v2.py",
        (
            "class ConversationService:\n    pass\n\n"
            "ConversationStoreV2 = ConversationService\n"
        ),
        "ConversationStoreV2",
    ),
)

#: Dynamic-import mutants (fix-round-1 gap): a forbidden module reached without
#: an import statement, through each banned mechanism.
DYNAMIC_IMPORT_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_importlib.py",
        'import importlib\n\n_memory = importlib.import_module("cmm.memory")\n',
        "importlib.import_module",
    ),
    (
        "mutant_importlib_from.py",
        'from importlib import import_module\n\n_memory = import_module("cmm.memory")\n',
        "importlib.import_module",
    ),
    (
        "mutant_dunder_import.py",
        '_memory = __import__("cmm.memory")\n',
        "__import__",
    ),
    (
        "mutant_sys_modules.py",
        'import sys\n\n_memory = sys.modules["cmm.memory"]\n',
        "sys.modules",
    ),
)

#: Alias/attribute mutants (fix-round-1 gap): the forbidden module reached
#: through a bound name, so the offender message must name that form.
ALIAS_ATTRIBUTE_MUTANTS: tuple[tuple[str, str, str], ...] = (
    (
        "mutant_alias_attribute.py",
        "import cmm as alias\n\n\ndef _reach():\n    return alias.memory\n",
        "alias.memory -> cmm.memory",
    ),
    (
        "mutant_getattr.py",
        'import cmm\n\n\ndef _reach():\n    return getattr(cmm, "memory")\n',
        "getattr reach cmm with the attribute name 'memory' -> cmm.memory",
    ),
)

#: The legitimate control the alias/attribute rule must admit: a bare ``cmm``
#: import that only touches sanctioned entries produces no attribute offender
#: (the bare import itself still fails the base allowlist rule by design).
ALIAS_ATTRIBUTE_CONTROL: tuple[str, str] = (
    "control_alias_attribute.py",
    "import cmm\n\n\ndef _reach():\n    return cmm.conversation\n",
)

#: The legitimate control the structural rules must admit: a benign class, a
#: benign dynamic construction, a benign alias, runtime type introspection and
#: an allowed attribute read.
STRUCTURAL_RULE_CONTROL: tuple[str, str] = (
    "control_structural_rules.py",
    (
        "from dataclasses import make_dataclass\n"
        "import cmm\n"
        "\n"
        "\n"
        "class DraftNote:\n"
        '    public_note: str = ""\n'
        "\n"
        "\n"
        "def _type_name(value: object) -> str:\n"
        "    return type(value).__name__\n"
        "\n"
        "\n"
        '_Created = type("DraftNote", (), {})\n'
        '_Row = make_dataclass("DraftNote", [("public_note", str)])\n'
        "DraftNoteAlias = DraftNote\n"
        "\n"
        "\n"
        "def _reach() -> object:\n"
        "    return cmm.conversation\n"
    ),
)

#: Fragment-drift probes (fix-round-1 gap): a synthetic production denial the
#: gate does not screen, and a production denial the gate lost, must both be
#: reported by the drift checker instead of escaping silently.
FRAGMENT_DRIFT_PROBES: tuple[tuple[str, tuple[str, ...], tuple[str, ...], str], ...] = (
    (
        "production-adds-a-denial",
        (*SECRET_LIKE_METADATA_KEYS, "vault_passphrase"),
        FORBIDDEN_SERIALIZED_FRAGMENTS,
        "vault_passphrase",
    ),
    (
        "gate-loses-a-production-denial",
        SECRET_LIKE_METADATA_KEYS,
        tuple(
            fragment
            for fragment in FORBIDDEN_SERIALIZED_FRAGMENTS
            if fragment != "cookie"
        ),
        "cookie",
    ),
)

#: Gate-widening probes: a fragment neither production nor the frozen
#: gate-only list names must be reported (a silent widening is a defect too).
GATE_WIDENING_PROBES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "gate-adds-an-undeclared-fragment",
        (*FORBIDDEN_SERIALIZED_FRAGMENTS, "raw_reasoning"),
        "raw_reasoning",
    ),
)

#: Runtime-probe mutants (fix-round-1 transitive gap): the violation is written
#: in the real layout (``cmm/conversation/probe.py``) of a minimal stub root,
#: and each row reaches a forbidden module through a different mechanism —
#: a binding, a from-import, a re-exporting seam and a bound dynamic import.
RUNTIME_IMPORT_MUTANTS: tuple[tuple[str, tuple[tuple[str, str], ...], str], ...] = (
    (
        "forbidden-import-binding",
        (("cmm/conversation/probe.py", "import cmm.memory\n"),),
        "cmm.memory",
    ),
    (
        "forbidden-from-import-binding",
        (
            (
                "cmm/conversation/probe.py",
                "from cmm.memory import TechnicalMemory\n",
            ),
        ),
        "TechnicalMemory",
    ),
    (
        "re-exporting-seam",
        (
            ("cmm/conversation/seam.py", "import cmm.memory as memory_gate\n"),
            (
                "cmm/conversation/probe.py",
                "from cmm.conversation.seam import memory_gate\n",
            ),
        ),
        "cmm.memory",
    ),
    (
        "bound-dynamic-import",
        (
            (
                "cmm/conversation/probe.py",
                (
                    "import importlib\n\n"
                    '_reached = importlib.import_module("cmm.memory")\n'
                ),
            ),
        ),
        "cmm.memory",
    ),
)


def _import_evasion_ids() -> list[str]:
    return [
        f"{module.replace('.', '_')}-{index}"
        for index, (_, module) in enumerate(IMPORT_EVASION_FORMS)
    ]


def _mutant_ids(rows: Sequence[Sequence[object]]) -> list[str]:
    return [str(row[0]).replace(".", "_").replace("/", "_") for row in rows]


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


def _nested_metadata_at_depth(key: str, depth: int) -> dict[str, object]:
    """Nest *key* inside *depth* mappings — the recursion-boundary probe."""

    payload: dict[str, object] = {key: "sk-attacker"}
    for level in range(depth - 1, 0, -1):
        payload = {f"level-{level}": payload}
    return payload


def _deepest_attacker_metadata(key: str) -> dict[str, object]:
    """Return *key* at the deepest mapping level the public recursion admits.

    ``MAX_METADATA_DEPTH`` nested mappings is that level; the bound is a
    measured fact pinned by
    ``test_the_recursion_boundary_is_where_the_deepest_payload_says_it_is``
    (one mapping deeper fails the bound itself), not an assumption.
    """

    return _nested_metadata_at_depth(key, MAX_METADATA_DEPTH)


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
    ``registry``, ``engine``, ``runtime``, ``planner``, ``router`` or
    ``manager`` — with a trailing version marker ignored, so
    ``ConversationPermissionManager`` and ``ConversationStoreV2`` are owner
    forms too — is a parallel authority by rule; the exact allowlist is empty
    because every such owner stays with its canonical lower layer.
    """

    owner_shaped = find_owner_shaped_classes(CONVERSATION_PACKAGE)

    assert owner_shaped == set(ALLOWED_NEW_OWNER_CLASSES), (
        f"cmm.conversation may not introduce an owner: {sorted(owner_shaped)}"
    )


def test_the_real_package_class_vocabulary_is_owner_free_and_the_scan_is_live() -> None:
    """The real class list carries no owner form, and the scan really sees it.

    The owner-family rules must not over-block the 18 real classes (the fix
    report lists them); the non-zero class count proves the scan is live, so an
    empty scan cannot pass this test by accident.
    """

    offenders = find_parallel_authority_offenders(CONVERSATION_PACKAGE)
    defined = {
        name
        for names in _classes_by_module(CONVERSATION_PACKAGE).values()
        for name in names
    }

    assert len(defined) > 0, "the class scan read no class at all"
    assert not offenders, (
        f"parallel authority defined in cmm.conversation: {sorted(offenders)}"
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


def test_conversation_package_uses_no_dynamic_import_machinery() -> None:
    """``importlib.import_module``, ``__import__`` and ``sys.modules`` are banned.

    Static extraction cannot see a dynamic import's target, so the mechanism
    itself is the offender (fix-round-1 evasion gap): the boundary has no
    legitimate need for any of the three.
    """

    offenders = find_dynamic_import_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        f"cmm.conversation must not use dynamic import machinery: {offenders}"
    )


def test_conversation_package_builds_no_dynamic_identifier() -> None:
    """No ``type``/``make_dataclass``/``setattr``/``exec`` builds a forbidden name.

    The class-statement scan cannot see a constructed identifier, so the
    construction itself is screened against the frozen owner and
    hidden-reasoning vocabulary (fix-round-1 evasion gap).
    """

    offenders = find_dynamic_identifier_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        "cmm.conversation must not construct an owner or hidden-reasoning "
        f"name dynamically: {offenders}"
    )


def test_conversation_package_exports_no_forbidden_alias() -> None:
    """No module-level assignment exports a forbidden owner name."""

    offenders = find_exported_alias_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        f"cmm.conversation must not export an owner alias: {offenders}"
    )


def test_conversation_package_reaches_no_forbidden_module_through_an_alias() -> None:
    """No ``cmm`` alias attribute read or ``getattr`` reaches a forbidden module."""

    offenders = find_alias_attribute_offenders(CONVERSATION_PACKAGE)

    assert not offenders, (
        "cmm.conversation must not reach a forbidden module through an alias "
        f"or getattr: {offenders}"
    )


def test_no_forbidden_module_is_reached_at_runtime() -> None:
    """A fresh subprocess imports every package module and reports its reaches.

    Three attribution lenses (see ``_RUNTIME_PROBE``): what the package binds
    into its namespaces, what its modules import, and what they load beyond the
    sanctioned seams' own closure.  The transitive gap (an allowed seam
    re-exporting a forbidden module) is exactly what the binding lens catches.
    The blanket "no forbidden module anywhere in the delta" form was measured
    and cannot hold — the Phase 10.45 seam's own package init eagerly imports
    the domain world — so this check attributes that pre-existing production
    behavior instead of hiding it.
    """

    module_names = [
        _module_dotted_name(path, CONVERSATION_PACKAGE_DOTTED, CONVERSATION_PACKAGE)
        for path in _package_files(CONVERSATION_PACKAGE)
    ]

    import_offenders, binding_offenders, closure_offenders = (
        find_runtime_import_offenders(
            module_names,
            root=REPO_ROOT,
            baseline_modules=RUNTIME_SEAM_BASELINE,
        )
    )

    assert not import_offenders, (
        "a conversation module imports into a forbidden package at runtime: "
        f"{import_offenders}"
    )
    assert not binding_offenders, (
        "a forbidden module is bound into a conversation module's namespace: "
        f"{binding_offenders}"
    )
    assert not closure_offenders, (
        "importing the package loads a forbidden module beyond the sanctioned "
        f"seams' own closure: {closure_offenders}"
    )


def test_the_internal_import_allowlist_is_live_and_pinned_per_module() -> None:
    """Every allowlist entry is live and every module's usage is frozen.

    The pin fails loudly in both directions: a module that stops importing its
    allowed entry (a stale allowlist) and a module that acquires a new entry or
    appears unexplained (a widened seam) are both a mismatch.  Keys are
    package-relative paths, so a future subpackage cannot collide with a
    top-level basename.
    """

    observed = {
        _relative_file_key(path, CONVERSATION_PACKAGE): _internal_entries_used(path)
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
    """Every layer is scanned at its REAL path, and the scan is anchored live.

    The pre-fix gate joined the dotted layer name onto the root and rglobbed
    ``<repo>/cmm.runtime`` — a path that does not exist — so five of six layers
    always reported zero offenders (the fix-round-1 Critical).  The finder now
    scans ``repo_root.joinpath(*layer.split("."))`` and its liveness anchor
    fails loudly on a missing or empty layer.
    """

    scanned = _scanned_layer_files(REPO_ROOT, layer)
    offenders = [
        entry
        for entry in find_reverse_dependency_offenders(REPO_ROOT, layer)
        if _matches_entry(entry.split(" -> ", 1)[1], target)
    ]

    assert len(scanned) > 0, f"{layer} was scanned as an empty directory"
    assert not offenders, f"{layer} must not import {target}: {sorted(offenders)}"


@pytest.mark.parametrize(
    "layer", REVERSE_DEPENDENCY_LAYERS, ids=lambda value: value.replace(".", "_")
)
def test_every_reverse_dependency_layer_is_really_scanned(layer: str) -> None:
    """The liveness anchor: the layer's real directory exists and holds files.

    A deleted, moved or empty layer must fail this test, never pass as a clean
    zero-offender scan.
    """

    files = _scanned_layer_files(REPO_ROOT, layer)

    assert len(files) > 0
    assert all(path.name.endswith(".py") for path in files)


def test_the_reverse_dependency_gate_fails_loudly_on_a_deleted_or_moved_layer() -> None:
    """Missing, dotted-name-only and empty layers all fail the anchor loudly.

    The last step admits the real layout, so the anchor is a boundary and not a
    blanket failure.
    """

    root = Path(tempfile.mkdtemp(prefix="cmm-conversation-liveness-"))
    try:
        # The layer is gone entirely (deleted or moved out of the repo).
        with pytest.raises(AssertionError, match="is missing"):
            find_reverse_dependency_offenders(root, "cmm.runtime")

        # A directory with the DOTTED name is not the real layout the gate
        # scans — the pre-fix pin used exactly this shape and hid the defect.
        (root / "cmm.runtime").mkdir()
        with pytest.raises(AssertionError, match="is missing"):
            find_reverse_dependency_offenders(root, "cmm.runtime")

        # The real layout, but its Python files were moved away.
        (root / "cmm" / "runtime").mkdir(parents=True)
        with pytest.raises(AssertionError, match="holds no Python file"):
            find_reverse_dependency_offenders(root, "cmm.runtime")

        # The real layout with a real file is scanned: the anchor admits it.
        (root / "cmm" / "runtime" / "__init__.py").write_text("", encoding="utf-8")

        assert find_reverse_dependency_offenders(root, "cmm.runtime") == ()
    finally:
        shutil.rmtree(root, ignore_errors=True)


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


def test_no_fragment_remains_gate_only_while_the_runtime_accepts_mappings() -> None:
    """Remediation MAJOR-03: the runtime screen, not the gate, is load-bearing.

    The V1 audit reproduced the gate-only fragments (``private_reasoning``,
    ``raw_prompt``) being accepted by the production runtime screen while the
    static walker screened them, so the gate was stronger only on paper.  Every
    fragment below must now fail closed at production construction time, and no
    fragment may sit in the frozen gate-only list while it does.
    """

    assert GATE_ONLY_SERIALIZED_FRAGMENTS == ()
    production = set(production_denied_fragments())
    for fragment, spelling in (
        ("privatereasoning", "private_reasoning"),
        ("rawprompt", "rawPrompt"),
        ("systemprompt", "system_prompt"),
        ("prompt", "prompt"),
    ):
        assert fragment in production
        with pytest.raises(ValueError):
            _message(metadata={spelling: "value"})


def test_the_serialized_fragment_gate_covers_every_production_denial() -> None:
    """The gate's fragment set is a superset of the production key screen.

    A future production denial must not silently escape the walker (fix-round-1
    gap: the hand-duplicated list had drifted both ways — production denied
    ``passwd``, ``privatekey``, ``cookie``, ``stacktrace`` and
    ``hiddenreasoning``, which the gate did not screen).  The gate may add
    entries only through ``GATE_ONLY_SERIALIZED_FRAGMENTS``, and every listed
    fragment is proven load-bearing.
    """

    production = production_denied_fragments()

    assert find_fragment_gate_drift(production, FORBIDDEN_SERIALIZED_FRAGMENTS) == [], (
        "the serialization gate does not screen a production denial: "
        f"{find_fragment_gate_drift(production, FORBIDDEN_SERIALIZED_FRAGMENTS)}"
    )
    assert (
        find_undeclared_gate_fragments(
            FORBIDDEN_SERIALIZED_FRAGMENTS, production, GATE_ONLY_SERIALIZED_FRAGMENTS
        )
        == []
    ), "a gate fragment is neither production's nor declared as deliberate"
    assert set(GATE_ONLY_SERIALIZED_FRAGMENTS) <= set(FORBIDDEN_SERIALIZED_FRAGMENTS)

    for fragment in FORBIDDEN_SERIALIZED_FRAGMENTS:
        assert find_serialized_fragment_offenders({fragment: "value"}), (
            f"the listed fragment is not load-bearing: {fragment!r}"
        )


@pytest.mark.parametrize(
    ("probe", "production", "gate", "expected"),
    FRAGMENT_DRIFT_PROBES,
    ids=_mutant_ids(FRAGMENT_DRIFT_PROBES),
)
def test_the_fragment_drift_probe_kills_a_production_denial_drift(
    probe: str, production: tuple[str, ...], gate: tuple[str, ...], expected: str
) -> None:
    """The drift checker reports a new production denial the gate does not screen."""

    drift = find_fragment_gate_drift(production, gate)

    assert drift, f"the drift checker survived its own violation: {probe}"
    assert expected in drift, drift


@pytest.mark.parametrize(
    ("probe", "gate", "expected"),
    GATE_WIDENING_PROBES,
    ids=_mutant_ids(GATE_WIDENING_PROBES),
)
def test_the_gate_widening_probe_kills_an_undeclared_fragment(
    probe: str, gate: tuple[str, ...], expected: str
) -> None:
    """A gate fragment nobody declared is reported (a silent widening is a defect)."""

    undeclared = find_undeclared_gate_fragments(
        gate, production_denied_fragments(), GATE_ONLY_SERIALIZED_FRAGMENTS
    )

    assert undeclared, f"the widening checker survived its own violation: {probe}"
    assert expected in undeclared, undeclared


def test_the_deepest_attacker_metadata_payload_is_rejected_at_construction() -> None:
    """The deepest admissible attacker payload fails closed at construction.

    The payload carries a secret-shaped key at the deepest mapping level the
    public recursion admits — ``MAX_METADATA_DEPTH`` nested mappings, the bound
    pinned explicitly by
    ``test_the_recursion_boundary_is_where_the_deepest_payload_says_it_is``;
    the identical shape with a benign key is accepted, so the rejection is the
    key screen and not the recursion bound.  Because construction raises, no
    turn can carry the payload — it is never silently sanitized into a storable
    value.  The ``from_dict`` re-read rejects it the same way, so a persisted
    payload cannot be read back either.
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


@pytest.mark.parametrize("depth", range(1, MAX_METADATA_DEPTH + 1))
def test_the_attacker_key_is_rejected_at_every_admissible_depth(depth: int) -> None:
    """A secret-shaped key fails the screen at every depth the grammar admits."""

    assert _message(metadata=_nested_metadata_at_depth("note", depth)).metadata

    with pytest.raises(ValueError):
        _message(metadata=_nested_metadata_at_depth(ATTACKER_METADATA_KEY, depth))


def test_the_recursion_boundary_is_where_the_deepest_payload_says_it_is() -> None:
    """The pinned recursion boundary: the deepest payload is accepted, +1 fails.

    ``MAX_METADATA_DEPTH`` nested mappings is the deepest the public recursion
    admits (the SPEC review read the pre-fix helper as one short of the
    boundary; the boundary is measured here instead of assumed), and one
    mapping deeper is rejected by the bound itself, so the deepest-payload
    helper rests on a pinned fact.
    """

    deepest = _deepest_attacker_metadata("note")
    one_deeper = {f"level-{MAX_METADATA_DEPTH}": deepest}

    assert _message(metadata=deepest).metadata

    with pytest.raises(ValueError, match="nest deeper"):
        _message(metadata=one_deeper)


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


# ── Mutation pins: every gate kills its own violation on a temp copy ─────────


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    PARALLEL_AUTHORITY_MUTANTS,
    ids=_mutant_ids(PARALLEL_AUTHORITY_MUTANTS),
)
def test_the_parallel_authority_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """The real violation injected into a temp copy makes the gate fail."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_parallel_authority_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders
        assert expected in find_owner_shaped_classes(package) or any(
            expected in entry
            for entry in find_named_authority_offenders(package, expected)
        ), offenders


@pytest.mark.parametrize(
    ("source", "module"),
    IMPORT_EVASION_FORMS,
    ids=_import_evasion_ids(),
)
def test_the_import_gate_catches_every_evasion_form(source: str, module: str) -> None:
    """Every evasion form injected into a temp copy is reported by a gate.

    The offender list is pinned de-duplicated: one import can be an offender of
    more than one rule (``kernel.llm`` is off the allowlist and a forbidden
    target) and the same offender string must be reported once.
    """

    with _mutable_package_copy(("probe.py", source)) as package:
        offenders = _import_gate_offenders(package)

        assert any(
            entry.split(" -> ", 1)[1] == module
            or entry.split(" -> ", 1)[1].startswith(f"{module}.")
            for entry in offenders
        ), f"evasion form not caught: {source!r}: {offenders}"
        assert len(offenders) == len(set(offenders)), offenders


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
    """A lower layer importing the boundary in a temp root makes the gate fail.

    The probe is injected in the REAL layout — ``<root>/cmm/runtime/probe.py``,
    which is the path the gate scans — and the offender must name that real
    relative path.  The pre-fix pin used a directory literally named
    ``cmm.runtime``, a shape this repository cannot take, so it passed while the
    gate scanned nothing (fix-round-1 Critical).
    """

    with _mutable_layer_copy(layer, source) as root:
        offenders = find_reverse_dependency_offenders(root, layer)
        real_probe = f"{layer.replace('.', '/')}/probe.py"

        assert any(
            entry.split(" -> ", 1)[1] == module
            or entry.split(" -> ", 1)[1].startswith(f"{module}.")
            for entry in offenders
        ), f"reverse dependency not caught: {source!r}: {offenders}"
        assert any(entry.startswith(f"{real_probe} -> ") for entry in offenders), (
            f"the offender must name the real layout path {real_probe}: {offenders}"
        )


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    HIDDEN_REASONING_MUTANTS,
    ids=_mutant_ids(HIDDEN_REASONING_MUTANTS),
)
def test_the_hidden_reasoning_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """A hidden-reasoning surface injected into a temp copy makes the gate fail."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_hidden_reasoning_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    OWNER_FAMILY_MUTANTS,
    ids=_mutant_ids(OWNER_FAMILY_MUTANTS),
)
def test_the_owner_family_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """Every owner-family mutant injected into a temp copy fails both rules.

    ``ConversationPermissionManager`` (the new ``manager`` token),
    ``ConversationStoreV2`` (a version marker on a frozen identity),
    ``ConversationApprovalManagerV2`` (both) and ``ConversationPermissionEngine2``
    (a version marker on an owner suffix) must all be owner-shaped by rule.
    """

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_parallel_authority_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders
        assert expected in find_owner_shaped_classes(package), (
            f"the owner-shape rule did not name {expected}: "
            f"{sorted(find_owner_shaped_classes(package))}"
        )


def test_the_owner_family_gate_admits_the_legitimate_control() -> None:
    """A value object and a version-suffixed non-owner are not owner-shaped."""

    probe, source = OWNER_FAMILY_CONTROL

    with _mutable_package_copy((probe, source)) as package:
        assert find_parallel_authority_offenders(package) == []


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    DYNAMIC_IDENTIFIER_MUTANTS,
    ids=_mutant_ids(DYNAMIC_IDENTIFIER_MUTANTS),
)
def test_the_dynamic_identifier_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """Every dynamic-construction shape injected into a temp copy fails the gate.

    ``type(name, bases, dict)``, ``make_dataclass`` (a class name and a
    hidden-reasoning field), ``setattr``, an ``exec`` code object and an opaque
    non-literal name are all covered (fix-round-1 gap).
    """

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_dynamic_identifier_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    EXPORTED_ALIAS_MUTANTS,
    ids=_mutant_ids(EXPORTED_ALIAS_MUTANTS),
)
def test_the_exported_alias_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """A module-level alias exporting an owner name fails the gate."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_exported_alias_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    DYNAMIC_IMPORT_MUTANTS,
    ids=_mutant_ids(DYNAMIC_IMPORT_MUTANTS),
)
def test_the_dynamic_import_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """Every banned dynamic-import mechanism fails the gate (fix-round-1 gap)."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_dynamic_import_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders


@pytest.mark.parametrize(
    ("probe", "source", "expected"),
    ALIAS_ATTRIBUTE_MUTANTS,
    ids=_mutant_ids(ALIAS_ATTRIBUTE_MUTANTS),
)
def test_the_alias_attribute_gate_kills_its_own_violation(
    probe: str, source: str, expected: str
) -> None:
    """The alias/attribute reach is reported with the form that made it."""

    with _mutable_package_copy((probe, source)) as package:
        offenders = find_alias_attribute_offenders(package)

        assert offenders, f"the gate survived its own violation: {source!r}"
        assert any(expected in entry for entry in offenders), offenders


def test_the_alias_attribute_gate_admits_the_legitimate_control() -> None:
    """A bare ``cmm`` import that only reads sanctioned entries is not an offender."""

    probe, source = ALIAS_ATTRIBUTE_CONTROL

    with _mutable_package_copy((probe, source)) as package:
        assert find_alias_attribute_offenders(package) == []


def test_the_structural_rules_admit_the_legitimate_control() -> None:
    """A benign class, construction, alias and attribute read pass every rule.

    The controls are the negative half of the fix-round-1 rules: a benign
    ``type``/``make_dataclass``, a benign module-level alias, runtime
    ``type(value).__name__`` introspection and an allowed ``cmm.conversation``
    attribute read must all stay unflagged.
    """

    probe, source = STRUCTURAL_RULE_CONTROL

    with _mutable_package_copy((probe, source)) as package:
        assert find_parallel_authority_offenders(package) == []
        assert find_dynamic_identifier_offenders(package) == []
        assert find_exported_alias_offenders(package) == []
        assert find_dynamic_import_offenders(package) == []
        assert find_alias_attribute_offenders(package) == []
        assert find_hidden_reasoning_offenders(package) == []


@pytest.mark.parametrize(
    ("probe", "probes", "expected"),
    RUNTIME_IMPORT_MUTANTS,
    ids=_mutant_ids(RUNTIME_IMPORT_MUTANTS),
)
def test_the_runtime_import_check_kills_its_own_violation(
    probe: str, probes: tuple[tuple[str, str], ...], expected: str
) -> None:
    """Each real-layout runtime violation of a stub root is reported.

    The stub root carries the real layout and importable forbidden stubs, so the
    runtime check is exercised against a violation exactly like every other
    gate; rows cover a module binding, a from-import binding, a re-exporting
    seam (the transitive gap) and a bound dynamic import.
    """

    with _mutable_runtime_copy(*probes) as root:
        import_offenders, binding_offenders, closure_offenders = (
            find_runtime_import_offenders(["cmm.conversation.probe"], root=root)
        )
        offenders = [*import_offenders, *binding_offenders, *closure_offenders]

        assert offenders, f"the runtime check survived its own violation: {probe}"
        assert any(expected in entry for entry in offenders), offenders
