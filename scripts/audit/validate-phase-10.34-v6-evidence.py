#!/usr/bin/env python3
"""Portable stdlib-only entrypoint for Phase 10.34 V6 evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    sys.path.insert(0, str(repo_root))

    from tests.domains.domain_session_audit_evidence import (
        EvidenceValidationError,
        validate_at_dp_034_bundle_evidence,
    )

    try:
        report = validate_at_dp_034_bundle_evidence(repo_root)
    except EvidenceValidationError as exc:
        print("AT_DP_034_PORTABLE_VALIDATION=FAIL")
        print(f"ERROR={exc}")
        return 1
    print("AT_DP_034_PORTABLE_VALIDATION=PASS")
    print(f"EVIDENCE_RESOLVED={report.evidence_resolved}/56")
    print(f"SOURCE_HASH_MANIFEST_SHA256={report.source_hash_manifest_sha256}")
    print(f"PYTEST_NODE_COUNT={len(report.collected_pytest_nodes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
