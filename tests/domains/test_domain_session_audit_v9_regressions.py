"""Phase 10.34 — Independent Audit V9 artifact-binding regressions."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tests.domains.domain_session_audit_evidence import (
    discover_latest_independent_audit,
    evaluate_phase_10_34_closure_eligibility,
)
from tests.domains.domain_session_lifecycle_test_support import (
    COMPLETE,
    EVIDENCE_VERSION,
    PENDING,
    _rebind_fixture_evidence,
    portable_archive_fixture,
    set_phase_10_34_documented_state,
    write_audit,
    write_audit_text,
)


def _source_manifest_digest(archive_root: Path) -> str:
    path = archive_root / (
        f"docs/audits/evidence/phase-10.34-v{EVIDENCE_VERSION}-source-hashes.json"
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pass_audit_text(version: int, digest: str | None) -> str:
    lines = [
        f"FINAL_INDEPENDENT_AUDIT_V{version}=PASS",
        "BLOCKERS=0",
        "MAJORS=0",
        "MINORS=0",
    ]
    if digest is not None:
        lines.append(f"AUDITED_SOURCE_HASH_MANIFEST_SHA256={digest}")
    return "\n".join((*lines, ""))


def test_01_matching_audit_source_manifest_digest_allows_closure(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    digest = _source_manifest_digest(archive_root)
    write_audit_text(archive_root, 10, _pass_audit_text(10, digest))

    audit = discover_latest_independent_audit(archive_root)
    closure = evaluate_phase_10_34_closure_eligibility(archive_root)

    assert audit is not None
    assert audit.audited_source_hash_manifest_sha256 == digest
    assert closure.closure_eligible is True


def test_02_changed_source_manifest_after_pass_revokes_closure(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    audited_digest = _source_manifest_digest(archive_root)
    write_audit_text(archive_root, 10, _pass_audit_text(10, audited_digest))

    source = archive_root / "tests/domains/test_domain_session_security.py"
    source.write_text(source.read_text(encoding="utf-8") + "\n# mutation\n")
    _rebind_fixture_evidence(archive_root)

    assert _source_manifest_digest(archive_root) != audited_digest
    assert (
        evaluate_phase_10_34_closure_eligibility(archive_root).closure_eligible is False
    )


def test_03_pass_without_source_manifest_digest_fails_closed(tmp_path: Path) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    write_audit_text(archive_root, 10, _pass_audit_text(10, None))

    assert (
        evaluate_phase_10_34_closure_eligibility(archive_root).closure_eligible is False
    )


def test_04_pass_with_malformed_source_manifest_digest_fails_closed(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    write_audit_text(archive_root, 10, _pass_audit_text(10, "not-a-sha256"))

    assert (
        evaluate_phase_10_34_closure_eligibility(archive_root).closure_eligible is False
    )


def test_05_fail_without_source_manifest_digest_remains_ineligible(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    write_audit(archive_root, 10, status="FAIL", blockers=0, majors=1, minors=0)

    audit = discover_latest_independent_audit(archive_root)
    closure = evaluate_phase_10_34_closure_eligibility(archive_root)

    assert audit is not None
    assert audit.status == "FAIL"
    assert closure.closure_eligible is False


def test_06_docs_only_complete_after_matching_pass_keeps_closure_eligible(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(
        tmp_path, status=PENDING, pending_audit_version=10
    )
    digest = _source_manifest_digest(archive_root)
    write_audit_text(archive_root, 10, _pass_audit_text(10, digest))
    set_phase_10_34_documented_state(archive_root, status=COMPLETE)

    closure = evaluate_phase_10_34_closure_eligibility(archive_root)

    assert _source_manifest_digest(archive_root) == digest
    assert closure.phase_status == COMPLETE
    assert closure.closure_eligible is True
