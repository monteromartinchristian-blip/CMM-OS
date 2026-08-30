"""Phase 10.34 V10 source-binding regressions for later-phase development."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.domains.domain_session_audit_evidence import (
    EvidenceValidationError,
    validate_at_dp_034_bundle_evidence,
)
from tests.domains.domain_session_lifecycle_test_support import (
    COMPLETE,
    portable_archive_fixture,
    write_audit,
)


def test_v10_validator_matches_audited_source_digest() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    validator = repo_root / "tests/domains/domain_session_audit_evidence.py"
    source_manifest = json.loads(
        (
            repo_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
        ).read_text(encoding="utf-8")
    )

    assert (
        hashlib.sha256(validator.read_bytes()).hexdigest()
        == source_manifest["files"]["tests/domains/domain_session_audit_evidence.py"]
    )


def _mutated_v10_fixture(tmp_path: Path, relative: str) -> Path:
    archive_root = portable_archive_fixture(tmp_path, status=COMPLETE)
    write_audit(archive_root, 10, status="PASS", blockers=0, majors=0, minors=0)
    source = archive_root / relative
    source.write_bytes(source.read_bytes() + b"\n# post-V10 mutation\n")
    return archive_root


def test_v10_binding_rejects_changed_cmm_main(tmp_path: Path) -> None:
    archive_root = _mutated_v10_fixture(tmp_path, "cmm/__main__.py")

    with pytest.raises(
        EvidenceValidationError, match="source hash mismatch: cmm/__main__.py"
    ):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_v10_binding_rejects_changed_validation_context(tmp_path: Path) -> None:
    archive_root = _mutated_v10_fixture(tmp_path, "cmm/domains/validation_context.py")

    with pytest.raises(
        EvidenceValidationError,
        match="source hash mismatch: cmm/domains/validation_context.py",
    ):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_v10_binding_rejects_changed_evidence_validator(tmp_path: Path) -> None:
    archive_root = _mutated_v10_fixture(
        tmp_path, "tests/domains/domain_session_audit_evidence.py"
    )

    with pytest.raises(
        EvidenceValidationError,
        match=("source hash mismatch: tests/domains/domain_session_audit_evidence.py"),
    ):
        validate_at_dp_034_bundle_evidence(archive_root)
