"""Phase 10.5 – Domain Validation Fragmentation Helpers.

Static analysis helpers for detecting architectural fragmentation:
duplicated system components, contract redefinition, backend bypass, etc.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence

# ── Fragmentation detection patterns ──────────────────────────────────────────

# Class names that indicate component duplication
_FRAGMENTATION_CLASS_NAMES: dict[str, str] = {
    "MemoryStore": "DOMAIN_FRAGMENTATION_MEMORY_DUPLICATION",
    "Planner": "DOMAIN_FRAGMENTATION_PLANNER_DUPLICATION",
    "AgentRuntime": "DOMAIN_FRAGMENTATION_AGENT_RUNTIME_DUPLICATION",
    "KnowledgeStore": "DOMAIN_FRAGMENTATION_KNOWLEDGE_STORE_DUPLICATION",
    "KnowledgeGraph": "DOMAIN_FRAGMENTATION_KNOWLEDGE_GRAPH_DUPLICATION",
    "ReasoningEngine": "DOMAIN_FRAGMENTATION_REASONING_ENGINE_DUPLICATION",
    "WorkflowEngine": "DOMAIN_FRAGMENTATION_WORKFLOW_ENGINE_DUPLICATION",
    "PermissionSystem": "DOMAIN_FRAGMENTATION_PERMISSION_SYSTEM_DUPLICATION",
    "SessionStore": "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
    "SessionContext": "DOMAIN_FRAGMENTATION_SESSION_INFRASTRUCTURE_DUPLICATION",
    "OperationResult": "DOMAIN_FRAGMENTATION_OPERATION_RESULT_DUPLICATION",
}

# Regex patterns for contract redefinition
_CONTRACT_REDEFINITION_PATTERNS: list[tuple[re.Pattern[str], str]] = []

# Protected canonical contract/model names (Phase 10.39)
_PROTECTED_CANONICAL_CONTRACT_NAMES = frozenset(
    {
        "KnowledgeItem",
        "Evidence",
        "TemporalScope",
        "Resource",
        "ResourceProvenance",
        "MemoryUpdateProposal",
        "DomainSessionContext",
        "DomainOperationResult",
    }
)

# Backend bypass patterns — superseded by AST-based detection in Phase 10.39
_BACKEND_BYPASS_PATTERNS: list[tuple[re.Pattern[str], str]] = []

# Provenance omission patterns
_PROVENANCE_OMISSION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"__version__\s*=\s*['\"]unknown['\"]", re.IGNORECASE),
        "DOMAIN_FRAGMENTATION_PROVENANCE_OMITTED",
    ),
]

# Policy bypass patterns (Phase 10.39: replaced by AST detection)
_POLICY_BYPASS_PATTERNS: list[tuple[re.Pattern[str], str]] = []

# Protected canonical bypass identifiers (Phase 10.39)
_POLICY_BYPASS_IDENTIFIERS = frozenset(
    {
        "skip_validation",
        "disable_validation",
        "bypass_validation",
        "skip_verification",
        "disable_verification",
        "bypass_verification",
        "skip_policy",
        "disable_policy",
        "bypass_policy",
    }
)

# Official CMM module prefixes — importing from these is OK (not duplication)
_OFFICIAL_CMM_PREFIXES = frozenset(
    {
        "cmm.",
        "cmm_agent.",
        "kernel.",
    }
)

# ── Component-aware canonical adapter bases (Phase 10.39 remediation) ─────────
# Only grant adapter exemption when the protected component's inherited/imported
# canonical base is actually the approved canonical base for that component.

_FRAGMENTATION_COMPONENT_NAMES: dict[str, str] = {
    "MemoryStore": "MemoryStore",
    "Planner": "Planner",
    "AgentRuntime": "AgentRuntime",
    "KnowledgeStore": "KnowledgeStore",
    "KnowledgeGraph": "KnowledgeGraph",
    "ReasoningEngine": "ReasoningEngine",
    "WorkflowEngine": "WorkflowEngine",
    "PermissionSystem": "PermissionSystem",
    "SessionStore": "SessionStore",
    "SessionContext": "SessionContext",
    "OperationResult": "OperationResult",
}

# Canonical base classes / symbols that legitimately correspond to each
# protected component.  A class may only receive adapter exemption when it
# inherits from or wraps a base that matches its own component category.
# Only actual repository symbols are listed.
_CANONICAL_ADAPTER_BASES_BY_COMPONENT: dict[str, frozenset[str]] = {
    "MemoryStore": frozenset(
        {
            "cmm.cognitive.resolution_memory.InMemoryResolutionMemoryStore",
            "cmm.cognitive.resolution_memory.ResolutionMemoryStore",
        }
    ),
    "Planner": frozenset(
        {
            "cmm.planner.task_planner.TaskPlanner",
        }
    ),
    "WorkflowEngine": frozenset(
        {
            "cmm.workflows.engine.WorkflowEngine",
        }
    ),
    "AgentRuntime": frozenset(),
    "KnowledgeStore": frozenset(),
    "KnowledgeGraph": frozenset(),
    "ReasoningEngine": frozenset(),
    "PermissionSystem": frozenset(),
    "SessionStore": frozenset(),
    "SessionContext": frozenset(),
    "OperationResult": frozenset(),
}

# ── Protected canonical global services (Phase 10.39 MAJOR-01) ────────────────
# Recreating these global architectural owners is forbidden even under a
# domain-specific name.  Uses exact suffixes grounded in real canonical owners.

_PROTECTED_SERVICE_SUFFIXES: dict[str, str] = {
    "DomainRegistry": "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
    "ResourceRegistry": "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
    "WorkflowRegistry": "DOMAIN_FRAGMENTATION_REGISTRY_DUPLICATION",
    "DomainResolver": "DOMAIN_FRAGMENTATION_RESOLVER_DUPLICATION",
    "DomainLoader": "DOMAIN_FRAGMENTATION_LOADER_DUPLICATION",
    "EventBus": "DOMAIN_FRAGMENTATION_EVENT_BUS_DUPLICATION",
    "TraceStore": "DOMAIN_FRAGMENTATION_TRACE_STORE_DUPLICATION",
}

# ── Protected persistence modules (Phase 10.39 MAJOR-02 import-aware) ─────────

_PERSISTENCE_IMPORT_MODULES: frozenset[str] = frozenset(
    {
        "sqlite3",
        "redis",
        "psycopg",
        "shelve",
    }
)

_PERSISTENCE_IMPORT_FROM_MODULES: frozenset[str] = frozenset(
    {
        "sqlalchemy",
    }
)

_PERSISTENCE_BACKEND_CALL_NAMES: frozenset[str] = frozenset(
    {
        "connect",
        "create_engine",
        "Redis",
    }
)

# ── Backend bypass protected imports (AST-based, Phase 10.39 MAJOR-02 9D) ────
# These module roots represent internal implementation boundaries that Domain
# Packs must not bypass directly.  Canonical API modules (cmm.planner,
# cmm.workflows, etc.) are NOT blocked here; they are the approved public
# interfaces.  Only internal/backend implementation submodules are protected.

_BACKEND_BYPASS_IMPORT_ROOTS: frozenset[str] = frozenset(
    {
        "cmm.memory.backend",
        "cmm.memory.store",
        "cmm.planner.backend",
        "cmm.runtime.backend",
        "cmm.execution.backend",
        "cmm.agent_runtime.agent_registry_store",
    }
)


def _is_safe_import(module_name: str | None) -> bool:
    """Check if an import is from an official CMM module (not duplication)."""
    if module_name is None:
        return True
    for prefix in _OFFICIAL_CMM_PREFIXES:
        if module_name.startswith(prefix):
            return True
    return False


def detect_class_duplication(
    content: str, rel_path: str, pack_module_prefixes: Sequence[str] = ()
) -> list[dict[str, object]]:
    """Detect class definitions that duplicate system components using AST.

    Only blocks when the class appears within the pack AND is not a permitted
    adapter. Imports from official CMM modules are not duplication.

    Phase 10.39 remediation: also detects recreated canonical global services
    (DomainRegistry, ResourceRegistry, etc.) using exact suffix matching.

    Args:
        content: Python source code as string.
        rel_path: Relative path of the file.
        pack_module_prefixes: Module prefixes that belong to the pack itself.

    Returns:
        List of findings dicts with 'line', 'class_name', 'code', 'path'.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    bindings = _collect_import_bindings(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            found = False
            # Check component duplication
            for class_name, finding_code in _FRAGMENTATION_CLASS_NAMES.items():
                if node.name == class_name or node.name.endswith(class_name):
                    is_adapter = _is_adapter_pattern(node, class_name, bindings)
                    if not is_adapter:
                        findings.append(
                            {
                                "line": node.lineno,
                                "class_name": node.name,
                                "code": finding_code,
                                "path": rel_path,
                            }
                        )
                    found = True
                    break
            # Check protected canonical service recreation (MAJOR-01 8A)
            if not found:
                for suffix, code in _PROTECTED_SERVICE_SUFFIXES.items():
                    if node.name.endswith(suffix):
                        is_adapter = _is_adapter_pattern(node, suffix, bindings)
                        if not is_adapter:
                            findings.append(
                                {
                                    "line": node.lineno,
                                    "class_name": node.name,
                                    "code": code,
                                    "path": rel_path,
                                }
                            )
                        break

    return findings


def _collect_import_bindings(tree: ast.AST) -> dict[str, str]:
    """Collect AST import bindings mapping local names to canonical module paths.

    Handles:
      - ``from cmm.planner import BasePlanner``
        → {"BasePlanner": "cmm.planner.BasePlanner"}
      - ``import cmm.planner as canonical_planner``
        → {"canonical_planner": "cmm.planner"}
      - ``import cmm.planner``
        → {"cmm": "cmm"}

    Phase 10.39 remediation: for ``from <package> import <Class>``, also
    resolves to the likely submodule path (e.g. ``cmm.planner.task_planner``)
    to match canonical base mappings that use full source-file paths.
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local_name = alias.asname or alias.name
                full_path = f"{node.module}.{alias.name}"
                bindings[local_name] = full_path
                # Also map to the likely submodule path for canonical-base matching
                # e.g. cmm.planner.TaskPlanner → cmm.planner.task_planner.TaskPlanner
                _add_submodule_binding(bindings, local_name, node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                bindings[local_name] = alias.name
    return bindings


# Map of known package → submodule for canonical base resolution.
# Only entries needed for adapter-base matching are listed here.
_KNOWN_SUBMODULES: dict[str, dict[str, str]] = {
    "cmm.planner": {
        "TaskPlanner": "cmm.planner.task_planner.TaskPlanner",
    },
    "cmm.cognitive": {
        "InMemoryResolutionMemoryStore": "cmm.cognitive.resolution_memory.InMemoryResolutionMemoryStore",
        "ResolutionMemoryStore": "cmm.cognitive.resolution_memory.ResolutionMemoryStore",
    },
    "cmm.workflows": {
        "WorkflowEngine": "cmm.workflows.engine.WorkflowEngine",
    },
}


def _add_submodule_binding(
    bindings: dict[str, str], local_name: str, module: str, attr: str
) -> None:
    """Add an alternative binding for the likely submodule path."""
    submodules = _KNOWN_SUBMODULES.get(module, {})
    if attr in submodules:
        bindings[local_name] = submodules[attr]


def _is_adapter_pattern(
    node: ast.ClassDef, class_name: str, bindings: dict[str, str]
) -> bool:
    """Check if a class is a permitted adapter (not duplication).

    Phase 10.39 remediation: adapter exemption is now component-aware.
    A protected architecture component may receive adapter exemption only
    when the inherited/imported canonical base is actually an approved
    canonical base for that specific protected component.

    Does NOT import or execute Domain Pack code.  Uses only a narrow
    immutable mapping of known canonical repository symbols.
    """
    # Resolve the component key (e.g. "MemoryStore") from the class name.
    component_key: str | None = None
    for frag_name, comp_key in _FRAGMENTATION_COMPONENT_NAMES.items():
        if class_name == frag_name or class_name.endswith(frag_name):
            component_key = comp_key
            break
    if component_key is None:
        return False

    approved_bases = _CANONICAL_ADAPTER_BASES_BY_COMPONENT.get(
        component_key, frozenset()
    )
    if not approved_bases:
        return False

    resolved_bases = _resolve_all_bases(node, bindings)
    for resolved in resolved_bases:
        if resolved in approved_bases:
            return True
    return False


def _resolve_all_bases(
    node: ast.ClassDef, bindings: dict[str, str]
) -> list[str]:
    """Resolve all base class names to full dotted module paths.

    Returns a list of resolved dotted strings such as
    ``"cmm.planner.task_planner.TaskPlanner"``.
    """
    resolved: list[str] = []
    for base in node.bases:
        base_path = _resolve_single_base(base, bindings)
        if base_path:
            resolved.append(base_path)
    return resolved


def _resolve_single_base(
    base: ast.expr, bindings: dict[str, str]
) -> str | None:
    """Resolve one base expression to a full dotted module path string."""
    if isinstance(base, ast.Attribute):
        raw = _resolve_attribute_path(base)
        if raw:
            parts = raw.split(".")
            if parts and parts[0] in bindings:
                resolved_prefix = bindings[parts[0]]
                remainder = ".".join(parts[1:])
                full_path = f"{resolved_prefix}.{remainder}" if remainder else resolved_prefix
                # Apply submodule resolution for the full path
                sub = _resolve_to_submodule(full_path)
                return sub if sub else full_path
            return raw
    elif isinstance(base, ast.Name):
        canonical = bindings.get(base.id, "")
        if canonical:
            sub = _resolve_to_submodule(canonical)
            return sub if sub else canonical
    return None


def _resolve_to_submodule(path: str) -> str | None:
    """Try to resolve an import path to its likely submodule source path.

    For example, ``cmm.planner.TaskPlanner`` → ``cmm.planner.task_planner.TaskPlanner``.
    Returns None if no known mapping exists.
    """
    parts = path.split(".")
    if len(parts) < 2:
        return None
    package = ".".join(parts[:-1])
    attr = parts[-1]
    submodules = _KNOWN_SUBMODULES.get(package, {})
    if attr in submodules:
        return submodules[attr]
    return None


def _resolve_attribute_path(node: ast.Attribute) -> str | None:
    """Resolve an Attribute AST node to a dotted module path string."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return ".".join(reversed(parts))
    return None


def detect_contract_redefinition(
    content: str, rel_path: str
) -> list[dict[str, object]]:
    """Detect classes that redefine protected CMM canonical contracts/models.

    Phase 10.39: Uses exact AST class-name matching against a protected
    canonical names set rather than broad regex heuristics.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ClassDef)
            and node.name in _PROTECTED_CANONICAL_CONTRACT_NAMES
        ):
            findings.append(
                {
                    "line": node.lineno,
                    "code": "DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION",
                    "path": rel_path,
                    "class_name": node.name,
                }
            )
    return findings


def detect_backend_bypass(content: str, rel_path: str) -> list[dict[str, object]]:
    """Detect direct backend access that bypasses architectural boundaries.

    Phase 10.39 remediation (MAJOR-02 9D): uses AST Import/ImportFrom
    analysis instead of raw-line regex, so comments and docstrings are
    never flagged.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if any(
                    alias.name == root or alias.name.startswith(root + ".")
                    for root in _BACKEND_BYPASS_IMPORT_ROOTS
                ):
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_BACKEND_BYPASS",
                            "path": rel_path,
                            "detail": alias.name,
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if any(
                node.module == root or node.module.startswith(root + ".")
                for root in _BACKEND_BYPASS_IMPORT_ROOTS
            ):
                findings.append(
                    {
                        "line": node.lineno,
                        "code": "DOMAIN_FRAGMENTATION_BACKEND_BYPASS",
                        "path": rel_path,
                        "detail": node.module,
                    }
                )

    return findings


def detect_provenance_omission(content: str, rel_path: str) -> list[dict[str, object]]:
    """Detect missing or omitted provenance information."""
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for pattern, code in _PROVENANCE_OMISSION_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "line": line_no,
                        "code": code,
                        "path": rel_path,
                        "match": line.strip()[:120],
                    }
                )
    return findings


def detect_policy_bypass(content: str, rel_path: str) -> list[dict[str, object]]:
    """Detect statically explicit validation/policy bypass identifiers.

    Phase 10.39: Uses AST inspection to detect explicit truthy bypass
    assignments and keyword arguments. Comments and docstrings are not flagged.
    Phase 10.39 remediation: handles ast.Attribute (dotted) targets and
    ast.AnnAssign (annotated) assignments.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = _extract_assign_final_name(target)
                if name in _POLICY_BYPASS_IDENTIFIERS and _is_truthy_value(node.value):
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
                            "path": rel_path,
                            "detail": name,
                        }
                    )
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                name = node.target.id
            elif isinstance(node.target, ast.Attribute):
                name = _extract_assign_final_name(node.target)
            else:
                name = ""
            if (
                name
                and name in _POLICY_BYPASS_IDENTIFIERS
                and node.value is not None
                and _is_truthy_value(node.value)
            ):
                findings.append(
                    {
                        "line": node.lineno,
                        "code": "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
                        "path": rel_path,
                        "detail": name,
                    }
                )
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg in _POLICY_BYPASS_IDENTIFIERS
                    and kw.value is not None
                    and _is_truthy_value(kw.value)
                ):
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
                            "path": rel_path,
                            "detail": kw.arg,
                        }
                    )

    return findings


def _extract_assign_final_name(target: ast.expr) -> str:
    """Extract the final attribute name from an assignment target.

    Phase 10.39 remediation: for ast.Attribute targets, extracts only the
    final attribute name (e.g. ``skip_validation`` from ``config.skip_validation``)
    instead of the full dotted path, so attribute-form bypasses are detected.
    """
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def _is_truthy_value(node: ast.expr) -> bool:
    """Check if an AST expression is a truthy constant."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    return False


# ── Phase 10.39 – Direct persistence / direct-write detection ─────────────────

def detect_direct_persistence_access(
    content: str,
    rel_path: str,
) -> list[dict[str, object]]:
    """Detect Domain Packs bypassing canonical persistence boundaries.

    Phase 10.39 remediation (MAJOR-01 8C, MAJOR-02 9A):
    - Uses AST inspection for both Import and ImportFrom.
    - Persistence calls are tied to statically known protected module/import
      bindings instead of relying on call-name suffixes alone.
    - ``client.connect()`` or local ``connect()`` are NOT flagged.
    - ``sqlite3.connect(...)`` and ``from sqlite3 import connect; connect(...)``
      ARE flagged.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    bindings = _collect_import_bindings(tree)

    # Track which local names are bound to persistence modules
    persistence_bindings: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                local_name = alias.asname or alias.name
                if top in _PERSISTENCE_IMPORT_MODULES:
                    persistence_bindings.add(local_name)
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
                            "path": rel_path,
                            "detail": alias.name,
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            top = node.module.split(".")[0]
            if top in _PERSISTENCE_IMPORT_FROM_MODULES:
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    persistence_bindings.add(local_name)
                findings.append(
                    {
                        "line": node.lineno,
                        "code": "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
                        "path": rel_path,
                        "detail": node.module,
                    }
                )
            # Also detect from-imports of protected persistence modules (8C)
            if top in _PERSISTENCE_IMPORT_MODULES:
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    persistence_bindings.add(local_name)
                findings.append(
                    {
                        "line": node.lineno,
                        "code": "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
                        "path": rel_path,
                        "detail": node.module,
                    }
                )
        elif isinstance(node, ast.Call):
            func_name = _resolve_call_name(node.func)
            if func_name:
                final_name = func_name.rsplit(".", 1)[-1]
                # Only flag persistence calls when the function is bound to
                # a known persistence module/import
                is_persistence_call = False
                if final_name in _PERSISTENCE_BACKEND_CALL_NAMES:
                    root = func_name.split(".")[0]
                    if root in persistence_bindings:
                        is_persistence_call = True
                    elif any(
                        root == mod or root.startswith(mod + ".")
                        for mod in _PERSISTENCE_IMPORT_MODULES
                    ):
                        is_persistence_call = True
                if is_persistence_call:
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS",
                            "path": rel_path,
                            "detail": func_name,
                        }
                    )

    return findings


def detect_direct_write(
    content: str,
    rel_path: str,
) -> list[dict[str, object]]:
    """Detect Domain Packs writing directly to the filesystem.

    Phase 10.39 remediation (MAJOR-02 9B, 9C):
    - ``open(path, 'w')`` is flagged only when ``open`` is the builtin
      (not shadowed by a local function or import).
    - ``Path(...).write_text(...)`` / ``write_bytes(...)`` is flagged only
      when the receiver is statically recognisable as ``pathlib.Path`` or
      an alias bound to ``pathlib.Path``.
    - ``writer.write_text(...)`` where ``writer`` is an arbitrary name is
      NOT flagged.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    bindings = _collect_import_bindings(tree)
    path_bindings = _collect_path_bindings(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check open(...) calls — only builtin open (9C)
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                if _is_builtin_open(node.func.id, tree) and _is_write_mode_open(
                    node
                ):
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_DIRECT_WRITE",
                            "path": rel_path,
                            "detail": "open(...)",
                        }
                    )
            # Check Path(...).write_text(...) and Path(...).write_bytes(...)
            elif isinstance(node.func, ast.Attribute) and node.func.attr in (
                "write_text",
                "write_bytes",
            ):
                if _receiver_is_path(node.func, path_bindings):
                    findings.append(
                        {
                            "line": node.lineno,
                            "code": "DOMAIN_FRAGMENTATION_DIRECT_WRITE",
                            "path": rel_path,
                            "detail": f".{node.func.attr}(...)",
                        }
                    )

    return findings


def _collect_path_bindings(tree: ast.AST) -> set[str]:
    """Collect local names that are bound to ``pathlib.Path`` or aliases."""
    path_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "pathlib" or node.module.startswith("pathlib."):
                for alias in node.names:
                    if alias.name == "Path":
                        local = alias.asname or alias.name
                        path_names.add(local)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pathlib":
                    local = alias.asname or alias.name
                    path_names.add(local)
    return path_names


def _receiver_is_path(
    func_attr: ast.Attribute, path_bindings: set[str]
) -> bool:
    """Check if the receiver of a method call is statically a pathlib.Path."""
    value = func_attr.value
    if isinstance(value, ast.Call):
        # Path(...) — check if the constructor name is a known Path binding
        if isinstance(value.func, ast.Name):
            return value.func.id in path_bindings
        if isinstance(value.func, ast.Attribute):
            # pathlib.Path(...)
            resolved = _resolve_attribute_path(value.func)
            if resolved and resolved.endswith("pathlib.Path"):
                return True
    elif isinstance(value, ast.Name):
        # Pre-bound variable: p = Path(...); p.write_text(...)
        # We cannot prove this without dataflow, but if the name is itself
        # a Path binding, allow it.  Otherwise, do NOT flag it.
        return value.id in path_bindings
    return False


def _is_builtin_open(name: str, tree: ast.AST) -> bool:
    """Check if ``open`` at module scope is the builtin (not shadowed)."""
    if name != "open":
        return False
    for node in ast.walk(tree):
        # Shadowed by import
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "open" or (
                    alias.asname and alias.asname == "open"
                ):
                    return False
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "open" or (
                    alias.asname and alias.asname == "open"
                ):
                    return False
        # Shadowed by function def at module level
        if isinstance(node, ast.FunctionDef) and node.name == "open":
            return False
    return True


def _resolve_call_name(node: ast.expr) -> str | None:
    """Resolve a Call func expression to a dotted name string."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _resolve_call_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _is_write_mode_open(call: ast.Call) -> bool:
    """Check if an open(...) call uses a write-capable mode.

    Returns True for modes containing 'w', 'a', 'x', or '+'.
    Returns False for read-only open calls (no mode, 'r', 'rb', etc.).
    """
    write_chars = {"w", "a", "x", "+"}

    # Check positional args (second arg is mode)
    if len(call.args) >= 2:
        mode_node = call.args[1]
        if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
            return any(c in mode_node.value for c in write_chars)

    # Check keyword args
    for kw in call.keywords:
        if (
            kw.arg == "mode"
            and isinstance(kw.value, ast.Constant)
            and isinstance(kw.value.value, str)
        ):
            return any(c in kw.value.value for c in write_chars)

    return False


def analyze_fragmentation(
    content: str,
    rel_path: str,
    *,
    pack_module_prefixes: Sequence[str] = (),
) -> list[dict[str, object]]:
    """Run all fragmentation checks on a single file.

    Args:
        content: File content as string.
        rel_path: Relative path of the file.
        pack_module_prefixes: Module prefixes belonging to the pack.

    Returns:
        List of all fragmentation findings for this file.
    """
    findings: list[dict[str, object]] = []

    findings.extend(detect_class_duplication(content, rel_path, pack_module_prefixes))
    findings.extend(detect_contract_redefinition(content, rel_path))
    findings.extend(detect_backend_bypass(content, rel_path))
    findings.extend(detect_direct_persistence_access(content, rel_path))
    findings.extend(detect_direct_write(content, rel_path))
    findings.extend(detect_provenance_omission(content, rel_path))
    findings.extend(detect_policy_bypass(content, rel_path))

    # De-duplicate: if a class is already caught by component duplication,
    # suppress the redundant contract-redefinition finding for the same class.
    seen_classes: set[str] = set()
    deduped: list[dict[str, object]] = []
    for f in findings:
        cls = str(f.get("class_name", ""))
        code = str(f.get("code", ""))
        if code == "DOMAIN_FRAGMENTATION_CONTRACT_REDEFINITION" and cls in seen_classes:
            continue
        if cls and code.endswith("_DUPLICATION"):
            seen_classes.add(cls)
        deduped.append(f)

    return deduped


__all__ = [
    "analyze_fragmentation",
    "detect_backend_bypass",
    "detect_class_duplication",
    "detect_contract_redefinition",
    "detect_direct_persistence_access",
    "detect_direct_write",
    "detect_policy_bypass",
    "detect_provenance_omission",
]
