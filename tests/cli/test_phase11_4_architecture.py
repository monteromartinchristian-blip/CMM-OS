"""Phase 11.4 — architecture gates for the one public CLI front door.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

Phase 11.4 adds a presentation layer beside the existing ``cmm/cli.py``: the
frozen public contracts, the deterministic renderer, the static command table
with its explicit dispatch, the thin application adapter and the read-only
doctor.  Those modules are the only new production surface of the phase, and
their architecture is part of the frozen design:

* **one front door** — the console script ``cmm = "cmm.cli:main"``, ``cmm/cli.py``
  as its wrapper, ``cmm/__main__.py`` as the root ``argparse`` tree, and no
  ``cmm/cli/`` package that would shadow the wrapper;
* **one framework** — ``argparse`` everywhere, and no Typer, Click, Fire,
  Docopt, Textual or prompt-toolkit anywhere under ``cmm`` or ``kernel``;
* **no parallel CLI authority** — no command registry, router, bus, runtime,
  engine, CLI service, state store, repository or history store;
* **dependency direction** — a presentation module may see the standard library,
  ``yaml``, ``cmm.application`` and its own siblings; the root entry point may
  additionally delegate to the grandfathered CLI facades it always delegated to.
  A canonical owner, a registry/store internal, an engine, a session store, a
  provider registry internal or an HTTP transport is never reachable from the
  presentation layer;
* **exact ownership** — ``CliApplicationAdapter`` owns one ``ApplicationGateway``
  and nothing else, ``CliDoctor`` owns one adapter plus immutable check metadata,
  and no presentation object names or holds a canonical owner.

The gates read the real production sources and the real live objects.  Their
rejection power is asserted too: the mutation checks at the end feed the very
same helpers a forbidden import and a parallel authority class and require them
to be caught.  A gate that quietly stopped rejecting would therefore fail here
instead of passing silently.  Nothing in this file mutates production, and the
grandfathered specialized CLIs (``cmm.validation.cli``, ``cmm.domains.sdk.cli``,
``cmm.agent_runtime.agent_runtime_cli``) are inspected by their own suites, not
rewritten here.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path

import pytest
import tomllib

from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.application import ApplicationGateway
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_commands import PHASE11_4_COMMANDS
from cmm.cli_contracts import CliAvailability, CliCommandDescriptor
from cmm.cli_doctor import CORE_CHECK_IDS, DOCTOR_CHECKS, CliDoctor, DoctorCheckSpec
from cmm.domains.registry import DomainRegistry
from cmm.runtime.sessions import InMemorySessionStore
from cmm.workflows.engine import WorkflowEngine
from kernel.llm.provider_registry import ProviderRegistry

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
CMM_PACKAGE = REPO_ROOT / "cmm"
KERNEL_PACKAGE = REPO_ROOT / "kernel"

# ── Frozen inventory of the front door ───────────────────────────────────────

#: The five Phase 11.4 presentation modules.  These are the modules this phase
#: introduces, and the only ones the presentation allowlist describes.
PHASE11_4_PRESENTATION_MODULES: tuple[Path, ...] = (
    CMM_PACKAGE / "cli_contracts.py",
    CMM_PACKAGE / "cli_output.py",
    CMM_PACKAGE / "cli_commands.py",
    CMM_PACKAGE / "cli_application.py",
    CMM_PACKAGE / "cli_doctor.py",
)

#: The two modules that own the public front door itself.
ROOT_ENTRYPOINT_MODULES: tuple[Path, ...] = (
    CMM_PACKAGE / "cli.py",
    CMM_PACKAGE / "__main__.py",
)

FRONT_DOOR_MODULES: tuple[Path, ...] = (
    *PHASE11_4_PRESENTATION_MODULES,
    *ROOT_ENTRYPOINT_MODULES,
)

#: The console script this project declares, and the one it must keep.
DECLARED_ENTRYPOINT = {"cmm": "cmm.cli:main"}

#: The ``cmm.*`` modules a presentation module may import: the application
#: boundary it adapts and its own siblings.  Nothing else.
PRESENTATION_ALLOWED_CMM_MODULES: tuple[str, ...] = (
    "cmm.application",
    "cmm.cli_application",
    "cmm.cli_commands",
    "cmm.cli_contracts",
    "cmm.cli_doctor",
    "cmm.cli_output",
)

#: The grandfathered specialized CLI facades the root entry point delegates to.
#: They exist before Phase 11.4, they own their historical dependencies and
#: their own suites prove their behavior; Phase 11.4 adds no dependency on them.
INHERITED_CLI_DELEGATION_MODULES: tuple[str, ...] = (
    "cmm.agent_runtime.agent_runtime_cli",
    "cmm.development",
    "cmm.domains.sdk.cli",
    "cmm.execution.development",
    "cmm.validation.cli",
)

#: The ``cmm.__main__`` root tree itself: ``cmm/cli.py`` is its wrapper, so the
#: console script delegates to the one root parser this phase preserves.
ROOT_PARSER_MODULE = "cmm.__main__"

#: The grandfathered kernel target the root ``run`` command always used.
INHERITED_KERNEL_DELEGATION_MODULES: tuple[str, ...] = ("kernel.end_to_end_runner",)

#: Third-party modules the presentation layer may import.  YAML is a declared
#: runtime dependency the renderer uses through ``yaml.safe_dump``.
ALLOWED_THIRD_PARTY_MODULES: tuple[str, ...] = ("yaml",)

#: CLI frameworks this phase must not adopt.  ``argparse`` is the frozen choice.
ALTERNATIVE_CLI_FRAMEWORKS: tuple[str, ...] = (
    "click",
    "docopt",
    "fire",
    "prompt_toolkit",
    "textual",
    "typer",
)

#: Parallel CLI authority classes the design forbids.  A registry, a router, a
#: bus, a runtime, an engine, a CLI service, a state store, a repository or a
#: history store would each be a second owner of the same presentation surface.
FORBIDDEN_PARALLEL_AUTHORITY_CLASSES: tuple[str, ...] = (
    "CLIHistoryStore",
    "CLIRepository",
    "CLIService",
    "CLIStateStore",
    "CMMCLIService",
    "CommandBus",
    "CommandEngine",
    "CommandRegistry",
    "CommandRouter",
    "CommandRuntime",
    "OperationalCLIService",
)

#: Canonical owners the presentation layer must never name, hold or reach.  The
#: list is the design's own: domain/agent/provider registries, session stores,
#: the workflow engine, the goal/approval owners, the plugin/backup/migration/
#: metrics owners of later phases, and the composition objects of the layers
#: below the application boundary.
FORBIDDEN_OWNER_IDENTIFIERS: frozenset[str] = frozenset(
    {
        "AgentRegistry",
        "AgentRegistryService",
        "ApplicationContainer",
        "ApprovalStore",
        "BackupService",
        "DomainRegistry",
        "ExecutorRegistry",
        "GoalManager",
        "GoalRepository",
        "GoalStore",
        "InMemorySessionStore",
        "InMemoryWorkflowRegistry",
        "IntegrationServiceRegistry",
        "MetricsStore",
        "MigrationEngine",
        "Orchestrator",
        "PluginRegistry",
        "ProviderRegistry",
        "SessionStore",
        "WorkflowEngine",
    }
)

#: Every forbidden parallel authority name, as one line-anchored class pattern.
#: This mirrors the repository-wide ``class`` gate the phase plan runs by hand.
FORBIDDEN_CLASS_PATTERN = re.compile(
    r"^class\s+(" + "|".join(FORBIDDEN_PARALLEL_AUTHORITY_CLASSES) + r")\b",
    re.MULTILINE,
)


def _module_id(path: Path) -> str:
    """Return one stable test id for a front-door module path."""

    return path.name


# ── Source helpers ───────────────────────────────────────────────────────────


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imported_modules(source: str) -> tuple[str, ...]:
    """Return every absolute module one source imports."""

    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
        elif isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
    return tuple(modules)


def _has_relative_imports(source: str) -> bool:
    """Return whether one source uses a relative import.

    The front door is made of top-level modules beside ``cmm/__init__.py``, so a
    relative import there is either broken or a sign that the file moved into a
    package -- which the frozen layout forbids.
    """

    return any(
        isinstance(node, ast.ImportFrom) and node.level > 0
        for node in ast.walk(ast.parse(source))
    )


def _disallowed_imports(
    source: str,
    *,
    allowed_cmm: tuple[str, ...] = PRESENTATION_ALLOWED_CMM_MODULES,
    allowed_kernel: tuple[str, ...] = (),
    allowed_third_party: tuple[str, ...] = ALLOWED_THIRD_PARTY_MODULES,
) -> list[str]:
    """Return every import the front-door allowlist does not sanction.

    The gate is an **allowlist**, not a denylist: the standard library and the
    declared third-party modules are allowed, a ``cmm.*`` import must be a frozen
    presentation sibling (or, for the root entry point, a grandfathered CLI
    facade), and a ``kernel.*`` import must be one of the grandfathered
    delegation targets.  A canonical owner, an engine, a registry or store
    internal, a session store, a provider registry internal, an HTTP transport
    and an alternative CLI framework are therefore all reported by construction
    rather than by being listed.
    """

    def _matches(module: str, allowed: tuple[str, ...]) -> bool:
        return any(
            module == prefix or module.startswith(f"{prefix}.") for prefix in allowed
        )

    disallowed: list[str] = []
    for module in _imported_modules(source):
        root = module.split(".", 1)[0]
        if root in sys.stdlib_module_names or _matches(module, allowed_third_party):
            continue
        if root == "cmm":
            if not _matches(module, allowed_cmm):
                disallowed.append(module)
            continue
        if root == "kernel":
            if module not in allowed_kernel:
                disallowed.append(module)
            continue
        disallowed.append(module)
    return sorted(set(disallowed))


def _defined_class_names(source: str) -> tuple[str, ...]:
    """Return every class one source defines."""

    return tuple(
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ClassDef)
    )


def _referenced_identifiers(source: str) -> frozenset[str]:
    """Return every identifier one source writes.

    Comments and string literals are excluded -- the gate is about what the code
    can reach, not about what a docstring discusses -- while an import binding
    (``from x import DomainRegistry``), an attribute alias
    (``module.DomainRegistry``), an annotation, a parameter, a class/function
    name, a keyword argument and an exception target are all collected, so no
    spelling of a canonical owner slips past the check.
    """

    identifiers: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            identifiers.add(node.id)
        elif isinstance(node, ast.Attribute):
            identifiers.add(node.attr)
        elif isinstance(node, ast.alias):
            identifiers.add(node.asname or node.name)
        elif isinstance(node, ast.arg):
            identifiers.add(node.arg)
        elif isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            identifiers.add(node.name)
        elif isinstance(node, ast.keyword) and node.arg:
            identifiers.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            identifiers.add(node.name)
        elif isinstance(node, ast.Global | ast.Nonlocal):
            identifiers.update(node.names)
    return frozenset(identifiers)


@lru_cache(maxsize=1)
def _repository_framework_importers() -> tuple[str, ...]:
    """Return production files that import an alternative CLI framework.

    The whole production tree is inspected, not only the front door: adopting a
    second CLI framework anywhere would split the public surface the design
    freezes into one ``argparse`` tree.
    """

    importers: list[str] = []
    for root in (CMM_PACKAGE, KERNEL_PACKAGE):
        for path in sorted(root.rglob("*.py")):
            modules = _imported_modules(_read(path))
            roots = {module.split(".", 1)[0] for module in modules}
            adopted = sorted(roots & set(ALTERNATIVE_CLI_FRAMEWORKS))
            if adopted:
                importers.append(f"{path.relative_to(REPO_ROOT)} -> {adopted}")
    return tuple(importers)


# ── One front door ───────────────────────────────────────────────────────────


def test_the_front_door_modules_exist() -> None:
    for path in FRONT_DOOR_MODULES:
        assert path.is_file(), f"missing front-door module: {path}"


def test_exactly_one_cmm_console_script_is_declared() -> None:
    """One project script, named ``cmm``, pointing at ``cmm.cli:main``."""

    declared = tomllib.loads(_read(PYPROJECT_PATH))["project"]["scripts"]

    assert declared == DECLARED_ENTRYPOINT


def test_the_console_script_target_resolves_to_a_callable() -> None:
    declared = tomllib.loads(_read(PYPROJECT_PATH))["project"]["scripts"]["cmm"]
    module_name, separator, attribute = declared.partition(":")

    assert separator == ":"

    module = importlib.import_module(module_name)

    assert callable(getattr(module, attribute))


def test_no_second_cli_package_shadows_the_console_script_wrapper() -> None:
    """``cmm/cli/`` would collide with ``cmm/cli.py`` and is forbidden."""

    assert (CMM_PACKAGE / "cli.py").is_file()
    assert not (CMM_PACKAGE / "cli").exists()


def test_no_second_project_script_exists() -> None:
    """No second console script may compete with the one front door."""

    declared = tomllib.loads(_read(PYPROJECT_PATH))["project"]["scripts"]

    assert len(declared) == 1
    assert set(declared) == {"cmm"}


# ── One framework: argparse ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "module",
    (CMM_PACKAGE / "cli_commands.py", CMM_PACKAGE / "__main__.py"),
    ids=_module_id,
)
def test_the_command_surface_is_registered_with_argparse(module: Path) -> None:
    assert "argparse" in _imported_modules(_read(module))


def test_the_root_parser_really_is_an_argparse_tree() -> None:
    import argparse

    from cmm.__main__ import build_parser

    parser = build_parser()

    assert type(parser) is argparse.ArgumentParser
    assert parser.prog == "cmm"


@pytest.mark.parametrize("module", FRONT_DOOR_MODULES, ids=_module_id)
def test_no_front_door_module_imports_an_alternative_cli_framework(
    module: Path,
) -> None:
    modules = _imported_modules(_read(module))
    adopted = sorted(
        {entry.split(".", 1)[0] for entry in modules} & set(ALTERNATIVE_CLI_FRAMEWORKS)
    )

    assert not adopted, f"{module.name} adopts an alternative CLI framework: {adopted}"


def test_no_production_module_imports_an_alternative_cli_framework() -> None:
    assert _repository_framework_importers() == ()


def test_no_alternative_cli_framework_is_a_declared_dependency() -> None:
    declared = tomllib.loads(_read(PYPROJECT_PATH))["project"]["dependencies"]
    names = {
        requirement.split(">", 1)[0].split("=", 1)[0].split("<", 1)[0].strip().lower()
        for requirement in declared
    }

    assert not names & set(ALTERNATIVE_CLI_FRAMEWORKS)


# ── No parallel CLI authority ────────────────────────────────────────────────


@pytest.mark.parametrize("name", FORBIDDEN_PARALLEL_AUTHORITY_CLASSES)
def test_no_front_door_module_defines_a_parallel_cli_authority(name: str) -> None:
    for path in FRONT_DOOR_MODULES:
        assert name not in _defined_class_names(_read(path)), (
            f"{path.name} defines the parallel CLI authority class {name}"
        )


def test_the_repository_defines_no_parallel_cli_authority_class() -> None:
    offenders: list[str] = []
    for root in (CMM_PACKAGE, KERNEL_PACKAGE):
        for path in sorted(root.rglob("*.py")):
            if FORBIDDEN_CLASS_PATTERN.search(_read(path)):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    assert not offenders, f"parallel CLI authority classes found: {offenders}"


# ── Dependency direction ─────────────────────────────────────────────────────


@pytest.mark.parametrize("module", PHASE11_4_PRESENTATION_MODULES, ids=_module_id)
def test_a_presentation_module_imports_only_the_frozen_allowlist(module: Path) -> None:
    source = _read(module)

    assert not _has_relative_imports(source), f"{module.name} uses a relative import"
    assert _disallowed_imports(source) == []


@pytest.mark.parametrize("module", ROOT_ENTRYPOINT_MODULES, ids=_module_id)
def test_the_root_entrypoint_delegates_only_to_inherited_cli_facades(
    module: Path,
) -> None:
    source = _read(module)

    assert not _has_relative_imports(source), f"{module.name} uses a relative import"
    assert (
        _disallowed_imports(
            source,
            allowed_cmm=(
                *PRESENTATION_ALLOWED_CMM_MODULES,
                *INHERITED_CLI_DELEGATION_MODULES,
                ROOT_PARSER_MODULE,
            ),
            allowed_kernel=INHERITED_KERNEL_DELEGATION_MODULES,
        )
        == []
    )


def test_the_presentation_allowlist_is_exact_and_live() -> None:
    """Every allowed sibling is really imported by the front door."""

    imported: set[str] = set()
    for path in FRONT_DOOR_MODULES:
        imported.update(_imported_modules(_read(path)))

    for allowed in PRESENTATION_ALLOWED_CMM_MODULES:
        assert any(
            module == allowed or module.startswith(f"{allowed}.") for module in imported
        ), f"stale allowlist entry: {allowed}"


def test_the_inherited_delegation_targets_are_real_grandfathered_modules() -> None:
    for name in (
        *INHERITED_CLI_DELEGATION_MODULES,
        *INHERITED_KERNEL_DELEGATION_MODULES,
    ):
        assert importlib.util.find_spec(name) is not None, name


def test_the_presentation_layer_reaches_no_canonical_owner_identifier() -> None:
    for module in PHASE11_4_PRESENTATION_MODULES:
        named = sorted(
            _referenced_identifiers(_read(module)) & FORBIDDEN_OWNER_IDENTIFIERS
        )

        assert not named, f"{module.name} names canonical owners: {named}"


def _forbidden_owner_types() -> tuple[type, ...]:
    """Return the canonical owner types that exist in this repository.

    The live gate is about the owners that are real today: the ones named in
    :data:`FORBIDDEN_OWNER_IDENTIFIERS` that are absent from the tree (plugin,
    backup, migration, metrics, goal-store and approval owners) are covered by
    the identifier gate above, which needs no import of a class that does not
    exist.
    """

    return (
        AgentRegistry,
        DomainRegistry,
        GoalManager,
        InMemorySessionStore,
        ProviderRegistry,
        WorkflowEngine,
    )


# ── Exact ownership of the live presentation objects ─────────────────────────


@pytest.fixture(scope="module")
def cli_objects() -> tuple[CliApplicationAdapter, CliDoctor]:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    return adapter, CliDoctor(adapter)


def test_the_cli_adapter_owns_only_the_application_gateway(
    cli_objects: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, _ = cli_objects
    owned = vars(adapter)

    assert set(owned) == {"_gateway"}
    # A subclass would be a second entrypoint of the same boundary.
    assert type(owned["_gateway"]) is ApplicationGateway
    assert not isinstance(adapter, _forbidden_owner_types())


def test_the_cli_doctor_owns_only_the_adapter_and_frozen_check_metadata(
    cli_objects: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = cli_objects

    assert set(vars(doctor)) == {"_application"}
    assert type(vars(doctor)["_application"]) is CliApplicationAdapter
    assert vars(doctor)["_application"] is adapter
    assert not isinstance(doctor, _forbidden_owner_types())


def test_the_presentation_metadata_is_static_and_immutable() -> None:
    assert isinstance(PHASE11_4_COMMANDS, tuple)
    assert isinstance(DOCTOR_CHECKS, tuple)

    command_ids = [descriptor.command_id for descriptor in PHASE11_4_COMMANDS]
    check_ids = [spec.check_id for spec in DOCTOR_CHECKS]

    # A table with a duplicate identity would be an ambiguous command surface.
    assert len(command_ids) == len(set(command_ids))
    assert len(check_ids) == len(set(check_ids))
    assert CORE_CHECK_IDS <= set(check_ids)

    descriptor = PHASE11_4_COMMANDS[0]
    spec = DOCTOR_CHECKS[0]

    assert isinstance(descriptor, CliCommandDescriptor)
    assert isinstance(descriptor.availability, CliAvailability)
    assert isinstance(spec, DoctorCheckSpec)
    assert dataclasses.is_dataclass(descriptor)
    assert dataclasses.is_dataclass(spec)

    with pytest.raises(dataclasses.FrozenInstanceError):
        descriptor.help = "changed"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.description = "changed"  # type: ignore[misc]


def test_no_presentation_object_is_a_canonical_owner(
    cli_objects: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = cli_objects

    for presentation_object in (adapter, doctor):
        assert not isinstance(presentation_object, _forbidden_owner_types())


# ── Mutation sanity checks (AST/string only; production is never mutated) ────


def test_the_import_gate_rejects_a_direct_domain_registry_import() -> None:
    source = "from cmm.domains.registry import DomainRegistry\n"

    assert _disallowed_imports(source) == ["cmm.domains.registry"]


def test_the_import_gate_rejects_runtime_store_and_registry_internals() -> None:
    source = (
        "import cmm.runtime.sessions\n"
        "from cmm.agent_runtime.agent_registry_store import InMemoryAgentRegistryStore\n"
        "from cmm.workflows.registry import InMemoryWorkflowRegistry\n"
        "from kernel.llm.provider_registry import ProviderRegistry\n"
        "from cmm.orchestration.orchestrator import Orchestrator\n"
        "from cmm.platform.container import ApplicationContainer\n"
        "import cmm.api\n"
    )

    assert _disallowed_imports(source) == [
        "cmm.agent_runtime.agent_registry_store",
        "cmm.api",
        "cmm.orchestration.orchestrator",
        "cmm.platform.container",
        "cmm.runtime.sessions",
        "cmm.workflows.registry",
        "kernel.llm.provider_registry",
    ]


def test_the_import_gate_rejects_an_alternative_cli_framework() -> None:
    assert _disallowed_imports("import typer\n") == ["typer"]
    assert _disallowed_imports("from click import command\n") == ["click"]


def test_the_import_gate_accepts_the_stdlib_and_the_frozen_allowlist() -> None:
    """The rejection gate must not be a gate that rejects everything."""

    source = (
        "from __future__ import annotations\n"
        "import argparse\n"
        "import json\n"
        "from collections.abc import Mapping\n"
        "from typing import TextIO\n"
        "import yaml\n"
        "from cmm.application import ApplicationGateway\n"
        "from cmm.cli_contracts import CliResult\n"
        "from cmm.cli_output import emit_cli_result\n"
        "from cmm.cli_application import CliApplicationAdapter\n"
        "from cmm.cli_doctor import CliDoctor\n"
    )

    assert _disallowed_imports(source) == []


def test_the_class_gate_rejects_a_parallel_command_registry() -> None:
    source = "class CommandRegistry:\n    pass\n"

    assert "CommandRegistry" in _defined_class_names(source)
    assert FORBIDDEN_CLASS_PATTERN.search(source)


def test_the_class_gate_rejects_every_forbidden_cli_authority_name() -> None:
    for name in FORBIDDEN_PARALLEL_AUTHORITY_CLASSES:
        source = f"class {name}:\n    pass\n"

        assert _defined_class_names(source) == (name,)
        assert FORBIDDEN_CLASS_PATTERN.search(source), name


def test_the_class_gate_accepts_the_frozen_table_and_descriptor() -> None:
    """A static metadata class is not a parallel authority."""

    for source in (
        "class CliCommandDescriptor:\n    pass\n",
        "class CliResult:\n    pass\n",
        "class CliDoctor:\n    pass\n",
        "class CliApplicationAdapter:\n    pass\n",
    ):
        assert not FORBIDDEN_CLASS_PATTERN.search(source)


def test_the_owner_gate_rejects_a_canonical_owner_identifier() -> None:
    names = _referenced_identifiers(
        "def build() -> DomainRegistry:\n"
        "    return DomainRegistry(store=InMemorySessionStore())\n"
    )

    assert names & FORBIDDEN_OWNER_IDENTIFIERS == {
        "DomainRegistry",
        "InMemorySessionStore",
    }


def test_the_owner_gate_ignores_prose_about_canonical_owners() -> None:
    """A docstring that explains the boundary is not a reference across it."""

    source = '"""The CLI never reaches the Orchestrator or the DomainRegistry."""\n'

    assert not _referenced_identifiers(source) & FORBIDDEN_OWNER_IDENTIFIERS
