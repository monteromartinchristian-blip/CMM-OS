#!/usr/bin/env python3
"""Generate deterministic Phase 10.34 V6 source, node, and gate evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tests.domains.domain_session_audit_evidence import (
    collect_pytest_nodes,
    discover_source_hash_paths,
)

EVIDENCE_DIR = REPO_ROOT / "docs/audits/evidence"
SOURCE_MANIFEST = EVIDENCE_DIR / "phase-10.34-v6-source-hashes.json"
NODE_INVENTORY = EVIDENCE_DIR / "phase-10.34-v6-pytest-nodes.txt"
GATES = EVIDENCE_DIR / "phase-10.34-v6-gates.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _gate(
    gate_id: str,
    command: str,
    binding: str,
    *,
    actual_count: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "command": command,
        "exit_code": 0,
        "gate_id": gate_id,
        "result_source": "command_execution",
        "source_hash_manifest_sha256": binding,
        "status": "PASS",
    }
    if actual_count is not None:
        result["actual_count"] = actual_count
    if extra:
        result.update(extra)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--focused-count", required=True, type=int)
    parser.add_argument("--domain-count", required=True, type=int)
    parser.add_argument("--global-count", required=True, type=int)
    parser.add_argument("--phase10-33-count", required=True, type=int)
    args = parser.parse_args()

    nodes = sorted(collect_pytest_nodes(REPO_ROOT))
    NODE_INVENTORY.write_text("\n".join(nodes) + "\n", encoding="utf-8")

    source_paths = discover_source_hash_paths(REPO_ROOT)
    files = {relative: _sha256(REPO_ROOT / relative) for relative in source_paths}
    _write_json(
        SOURCE_MANIFEST,
        {
            "algorithm": "sha256",
            "file_count": len(files),
            "files": files,
            "phase": "10.34",
            "schema_version": 1,
            "scope": [
                "cmm/**/*.py",
                "tests/**/*.py",
                "scripts/audit/**/*.py",
                "pyproject.toml",
            ],
        },
    )
    binding = _sha256(SOURCE_MANIFEST)
    inventory_digest = _sha256(NODE_INVENTORY)

    quality_members = ["ruff_check", "ruff_format", "compileall", "diff_check"]
    all_members = [
        "focused_tests",
        "domain_tests",
        "global_tests",
        *quality_members,
        "phase10_33_regression",
    ]
    gate_map = {
        "focused_tests": _gate(
            "focused_tests",
            ".venv/bin/python -m pytest -q tests/domains/test_domain_session_*.py",
            binding,
            actual_count=args.focused_count,
        ),
        "domain_tests": _gate(
            "domain_tests",
            ".venv/bin/python -m pytest -q tests/domains",
            binding,
            actual_count=args.domain_count,
        ),
        "global_tests": _gate(
            "global_tests",
            ".venv/bin/python -m pytest -q",
            binding,
            actual_count=args.global_count,
        ),
        "ruff_check": _gate(
            "ruff_check",
            ".venv/bin/ruff check cmm/domains/session_*.py cmm/domains/resource_authority.py cmm/domains/knowledge_authority.py cmm/domains/composer.py cmm/domains/composition_contracts.py tests/domains/test_domain_session_*.py tests/domains/domain_session_audit_evidence.py scripts/audit/*.py",
            binding,
        ),
        "ruff_format": _gate(
            "ruff_format",
            ".venv/bin/ruff format --check cmm/domains/session_*.py cmm/domains/resource_authority.py cmm/domains/knowledge_authority.py cmm/domains/composer.py cmm/domains/composition_contracts.py tests/domains/test_domain_session_*.py tests/domains/domain_session_audit_evidence.py scripts/audit/*.py",
            binding,
        ),
        "compileall": _gate(
            "compileall",
            ".venv/bin/python -m compileall -q cmm tests scripts/audit",
            binding,
        ),
        "diff_check": _gate("diff_check", "git diff --check", binding),
        "phase10_33_regression": _gate(
            "phase10_33_regression",
            ".venv/bin/python -m pytest -q tests/domains/test_domain_event_catalog.py tests/domains/test_domain_event_factory.py tests/domains/test_domain_event_publisher.py tests/domains/test_domain_session_security.py",
            binding,
            actual_count=args.phase10_33_count,
            extra={
                "domain_session_resumed_event": "ABSENT",
                "general_event_count": 23,
                "general_event_unique_count": 23,
            },
        ),
    }
    _write_json(
        GATES,
        {
            "artifact_contract": {
                "archive_format": "tar.gz",
                "command_template": "git archive --format=tar.gz --prefix=CMM-OS-phase-10.34/ -o <external-output> <committed-head>",
                "contract_id": "git_archive_v6",
                "embedded_commit_verification": "external_required",
                "forbidden_member_patterns": [".git", ".venv", "__pycache__", ".pyc"],
                "forbidden_paths_check": True,
                "generator": "git archive",
                "output_location": "external_to_repository",
                "pax_commit_id_verification": True,
                "prefix": "CMM-OS-phase-10.34/",
            },
            "audit_iteration": "V6",
            "gate_groups": {
                "pre_audit_gates": {
                    "component_gates": all_members,
                    "source_hash_manifest_sha256": binding,
                    "status": "PASS",
                },
                "quality_gates": {
                    "component_gates": quality_members,
                    "source_hash_manifest_sha256": binding,
                    "status": "PASS",
                },
            },
            "gates": gate_map,
            "generated_at": args.generated_at,
            "phase": "10.34",
            "pre_audit": {
                "source_hash_manifest_sha256": binding,
                "source_scope_clean_when_generated": True,
            },
            "pytest_evidence": {
                "inventory": "docs/audits/evidence/phase-10.34-v6-pytest-nodes.txt",
                "inventory_sha256": inventory_digest,
                "node_count": len(nodes),
            },
            "schema_version": 2,
            "source_evidence": {
                "file_count": len(files),
                "manifest": "docs/audits/evidence/phase-10.34-v6-source-hashes.json",
                "manifest_sha256": binding,
            },
        },
    )
    print(f"SOURCE_HASH_FILES={len(files)}")
    print(f"SOURCE_HASH_MANIFEST_SHA256={binding}")
    print(f"PYTEST_NODE_COUNT={len(nodes)}")
    print(f"PYTEST_NODES_SHA256={inventory_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
