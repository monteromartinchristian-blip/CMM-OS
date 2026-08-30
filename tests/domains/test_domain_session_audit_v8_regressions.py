"""Phase 10.34 — post-V8 lifecycle fixture isolation regressions."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.domains.domain_session_audit_evidence import (
    EvidenceValidationError,
    evaluate_phase_10_34_closure_eligibility,
    validate_at_dp_034_bundle_evidence,
)
from tests.domains.domain_session_lifecycle_test_support import (
    COMPLETE,
    PENDING,
    REPO_ROOT,
    copy_real_audit,
    portable_archive_fixture,
    write_audit,
)

LIFECYCLE_DOCUMENTS = (
    "ROADMAP.md",
    "docs/roadmap/phase-10-domain-intelligence.md",
    "docs/reference/domain-sessions.md",
    "docs/reference/domain-intelligence-requirements-matrix.md",
)


def _document_snapshot(root: Path) -> dict[str, bytes]:
    return {
        relative: (root / relative).read_bytes() for relative in LIFECYCLE_DOCUMENTS
    }


def test_18_closed_repo_fixture_with_clean_v8_pass_is_closure_eligible(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(tmp_path, status=COMPLETE)
    copy_real_audit(REPO_ROOT, archive_root, 8)

    report = validate_at_dp_034_bundle_evidence(archive_root)

    closure = report.resolved[56].details
    assert report.evidence_resolved == 56
    assert closure["phase_status"] == COMPLETE
    assert closure["latest_independent_audit"] == "V8"
    assert closure["latest_independent_audit_status"] == "PASS"
    assert closure["closure_eligible"] is True
    assert "Phase 10.35 — Domain SDK is next" in (
        archive_root / "ROADMAP.md"
    ).read_text(encoding="utf-8")
    matrix = (
        archive_root / "docs/reference/domain-intelligence-requirements-matrix.md"
    ).read_text(encoding="utf-8")
    assert "`DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS`" in matrix
    assert "re-audit V9 pending" not in matrix


def test_19_closed_repo_fixture_with_fail_fails_closed(tmp_path: Path) -> None:
    archive_root = portable_archive_fixture(tmp_path, status=COMPLETE)
    write_audit(archive_root, 8, status="FAIL", blockers=0, majors=1, minors=0)

    with pytest.raises(EvidenceValidationError, match="closed without a clean"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_20_closed_repo_fixture_with_pass_findings_fails_closed(
    tmp_path: Path,
) -> None:
    archive_root = portable_archive_fixture(tmp_path, status=COMPLETE)
    write_audit(archive_root, 8, status="PASS", blockers=0, majors=0, minors=1)

    with pytest.raises(EvidenceValidationError, match="PASS requires zero findings"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_21_pending_state_remains_valid_when_source_docs_are_complete(
    tmp_path: Path,
) -> None:
    closed_source = portable_archive_fixture(tmp_path / "closed", status=COMPLETE)
    pending_archive = portable_archive_fixture(
        tmp_path / "pending",
        source_root=closed_source,
        status=PENDING,
        pending_audit_version=9,
    )
    write_audit(pending_archive, 8, status="FAIL", blockers=0, majors=1, minors=0)

    report = validate_at_dp_034_bundle_evidence(pending_archive)

    closure = report.resolved[56].details
    assert closure["phase_status"] == PENDING
    assert closure["latest_independent_audit_status"] == "FAIL"
    assert closure["closure_eligible"] is False


def test_22_fixture_state_mutation_affects_temporary_copy_only(tmp_path: Path) -> None:
    pending_source = portable_archive_fixture(
        tmp_path / "source", status=PENDING, pending_audit_version=9
    )
    before = _document_snapshot(pending_source)

    closed_archive = portable_archive_fixture(
        tmp_path / "closed", source_root=pending_source, status=COMPLETE
    )

    assert _document_snapshot(pending_source) == before
    assert _document_snapshot(closed_archive) != before
    assert (
        evaluate_phase_10_34_closure_eligibility(pending_source).phase_status == PENDING
    )


def test_23_repo_source_documentation_is_never_modified_by_lifecycle_fixtures(
    tmp_path: Path,
) -> None:
    before = _document_snapshot(REPO_ROOT)

    portable_archive_fixture(
        tmp_path / "pending", status=PENDING, pending_audit_version=9
    )
    portable_archive_fixture(tmp_path / "complete", status=COMPLETE)

    assert _document_snapshot(REPO_ROOT) == before
