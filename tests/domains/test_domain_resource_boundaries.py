"""Tests for Phase 10.10 – Domain Resource boundary constraints (Task 11).

Static source scans confirming ``resource_*.py`` files never touch the
filesystem, network, persistence, OCR, embeddings, vector stores, Knowledge
Graph mutation, adapter execution, or broad exception handling.
"""

from __future__ import annotations

import re
from pathlib import Path

_RESOURCE_FILES = sorted(Path("cmm/domains").glob("resource_*.py"))

_FORBIDDEN_PATTERNS = {
    "filesystem": r"\bopen\(|\bPath\(.*\)\.write|\bos\.remove\b|\bshutil\b",
    "network": r"\brequests\.|\burllib\b|\bsocket\.|\bhttpx\b|\baiohttp\b",
    "persistence": r"\bsqlite3\b|\bsqlalchemy\b|\.save\(\)|\.commit\(\)",
    "ocr": r"\bpytesseract\b|\bocr\b",
    "embeddings": r"\bembedding\b|\bembed_text\b",
    "vector_stores": r"\bfaiss\b|\bchromadb\b|\bpinecone\b|\bqdrant\b",
    "knowledge_graph_mutation": r"\bKnowledgeGraph\b.*\.(add|remove|mutate)\(",
    "adapter_execution": r"\badapter\.execute\(|\badapter\.run\(|\.execute_adapter\(",
    "eval_exec": r"\beval\(|\bexec\(|\bcompile\(|\bimportlib\b",
    "broad_exception": r"except Exception|str\(exc\)|repr\(exc\)",
}


def test_resource_files_exist():
    assert len(_RESOURCE_FILES) >= 4


def test_no_forbidden_boundary_patterns():
    violations: list[str] = []
    for path in _RESOURCE_FILES:
        source = path.read_text()
        for label, pattern in _FORBIDDEN_PATTERNS.items():
            if re.search(pattern, source):
                violations.append(f"{path}: {label}")
    assert not violations, f"Forbidden boundary patterns found: {violations}"


def test_no_filesystem_or_network_imports():
    forbidden_imports = {
        "os",
        "shutil",
        "socket",
        "requests",
        "urllib",
        "httpx",
        "aiohttp",
        "sqlite3",
        "sqlalchemy",
    }
    for path in _RESOURCE_FILES:
        source = path.read_text()
        imported = set(
            re.findall(r"^\s*(?:import|from)\s+([\w.]+)", source, re.MULTILINE)
        )
        top_level = {name.split(".")[0] for name in imported}
        overlap = top_level & forbidden_imports
        assert not overlap, f"{path} imports forbidden modules: {overlap}"
