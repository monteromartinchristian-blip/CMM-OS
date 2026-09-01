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

# Backend bypass patterns
_BACKEND_BYPASS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(import|from)\s+cmm\.(memory|planner|runtime|execution)\.",
            re.IGNORECASE,
        ),
        "DOMAIN_FRAGMENTATION_BACKEND_BYPASS",
    ),
    (
        re.compile(r"\bopen\s*\(\s*['\"].*backend", re.IGNORECASE),
        "DOMAIN_FRAGMENTATION_BACKEND_BYPASS",
    ),
    (
        re.compile(
            r"\b(import|from)\s+cmm\.(agent_runtime\.agent_registry_store)",
            re.IGNORECASE,
        ),
        "DOMAIN_FRAGMENTATION_BACKEND_BYPASS",
    ),
]

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
            for class_name, finding_code in _FRAGMENTATION_CLASS_NAMES.items():
                if node.name == class_name or node.name.endswith(class_name):
                    # Check if this is an adapter (inherits from official CMM base)
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
    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local_name = alias.asname or alias.name
                bindings[local_name] = f"{node.module}.{alias.name}"
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name
                bindings[local_name] = alias.name
    return bindings


def _is_adapter_pattern(
    node: ast.ClassDef, class_name: str, bindings: dict[str, str]
) -> bool:
    """Check if a class is a permitted adapter (not duplication).

    An adapter would extend or wrap the official component, not reimplement it.
    Canonical imported bases are recognized through AST import bindings.
    """
    for base in node.bases:
        if isinstance(base, ast.Attribute):
            # e.g., cmm.memory.MemoryStore → importing/adapting, not reimplementing
            module_path = _resolve_attribute_path(base)
            if module_path:
                for prefix in _OFFICIAL_CMM_PREFIXES:
                    if module_path.startswith(prefix):
                        return True
                # Also check alias form: canonical_planner.BasePlanner
                # where canonical_planner is bound to cmm.planner
                parts = module_path.split(".")
                if parts and parts[0] in bindings:
                    resolved = bindings[parts[0]]
                    remainder = ".".join(parts[1:])
                    full_path = f"{resolved}.{remainder}" if remainder else resolved
                    for prefix in _OFFICIAL_CMM_PREFIXES:
                        if full_path.startswith(prefix):
                            return True
        elif isinstance(base, ast.Name):
            # Check import bindings: from cmm.planner import BasePlanner
            canonical = bindings.get(base.id, "")
            for prefix in _OFFICIAL_CMM_PREFIXES:
                if canonical.startswith(prefix):
                    return True
    return False


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
    """Detect direct backend access that bypasses architectural boundaries."""
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for pattern, code in _BACKEND_BYPASS_PATTERNS:
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
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = _extract_assign_target_name(target)
                if name in _POLICY_BYPASS_IDENTIFIERS and _is_truthy_value(node.value):
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


def _extract_assign_target_name(target: ast.expr) -> str:
    """Extract the simple name from an assignment target."""
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        parent = _extract_assign_target_name(target.value)
        if parent:
            return f"{parent}.{target.attr}"
    return ""


def _is_truthy_value(node: ast.expr) -> bool:
    """Check if an AST expression is a truthy constant."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    return False


# ── Phase 10.39 – Direct persistence / direct-write detection ─────────────────

_PERSISTENCE_IMPORT_MODULES = frozenset(
    {
        "sqlite3",
        "redis",
        "psycopg",
        "shelve",
    }
)

_PERSISTENCE_IMPORT_FROM_MODULES = frozenset(
    {
        "sqlalchemy",
    }
)

_PERSISTENCE_BACKEND_CALL_NAMES = frozenset(
    {
        "connect",
        "create_engine",
        "Redis",
    }
)


def detect_direct_persistence_access(
    content: str,
    rel_path: str,
) -> list[dict[str, object]]:
    """Detect Domain Packs bypassing canonical persistence boundaries.

    Uses AST inspection for:
    - ``import sqlite3``, ``import redis``, etc.
    - ``from sqlalchemy import create_engine``
    - ``sqlite3.connect(...)``, ``create_engine(...)``, ``redis.Redis(...)``, etc.
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
                if top in _PERSISTENCE_IMPORT_MODULES:
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
            if (
                func_name
                and func_name.rsplit(".", 1)[-1] in _PERSISTENCE_BACKEND_CALL_NAMES
                and not any(
                    f["line"] == node.lineno
                    and f["code"] == "DOMAIN_FRAGMENTATION_DIRECT_PERSISTENCE_ACCESS"
                    for f in findings
                )
            ):
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

    Uses AST inspection for:
    - ``open(path, 'w')``, ``open(path, 'a')``, ``open(path, 'x')``, ``open(path, mode='w+')``
    - ``Path(...).write_text(...)``
    - ``Path(...).write_bytes(...)``
    - Read-only ``open(path)`` and ``open(path, 'r')`` are NOT flagged.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check open(...) calls
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                if _is_write_mode_open(node):
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
                findings.append(
                    {
                        "line": node.lineno,
                        "code": "DOMAIN_FRAGMENTATION_DIRECT_WRITE",
                        "path": rel_path,
                        "detail": f".{node.func.attr}(...)",
                    }
                )

    return findings


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
