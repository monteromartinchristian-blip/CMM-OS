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

# Policy bypass patterns
_POLICY_BYPASS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\bbypass\s+(validation|verification|check|policy)\b",
            re.IGNORECASE,
        ),
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
    (
        re.compile(
            r"\bdisable\s+(validation|verification|check|policy)\b",
            re.IGNORECASE,
        ),
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
    (
        re.compile(
            r"\bskip\s+(validation|verification|check|policy)\b",
            re.IGNORECASE,
        ),
        "DOMAIN_FRAGMENTATION_POLICY_BYPASS",
    ),
]

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
        if isinstance(node, ast.ClassDef):
            if node.name in _PROTECTED_CANONICAL_CONTRACT_NAMES:
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
    """Detect patterns that bypass CMM global policies."""
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for pattern, code in _POLICY_BYPASS_PATTERNS:
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
    "detect_policy_bypass",
    "detect_provenance_omission",
]
