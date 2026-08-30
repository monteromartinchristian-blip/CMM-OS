"""Phase 10.34 — Domain Sessions — Independent Audit V6 regressions."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.domains.domain_session_audit_evidence import (
    EvidenceValidationError,
    discover_latest_independent_audit,
    evaluate_phase_10_34_closure_eligibility,
    validate_at_dp_034_bundle_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _portable_archive_fixture(tmp_path: Path) -> Path:
    archive_root = tmp_path / "CMM-OS-phase-10.34"
    source_manifest_path = (
        REPO_ROOT / "docs/audits/evidence/phase-10.34-v7-source-hashes.json"
    )
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    required_paths = set(source_manifest["files"])
    required_paths.update(
        {
            "ROADMAP.md",
            "docs/audits/evidence/phase-10.34-at-dp-034-manifest.json",
            "docs/audits/evidence/phase-10.34-v7-gates.json",
            "docs/audits/evidence/phase-10.34-v7-pytest-nodes.txt",
            "docs/audits/evidence/phase-10.34-v7-source-hashes.json",
            "docs/audits/phase-10.34-independent-audit-v6.md",
            "docs/reference/domain-sessions.md",
            "docs/roadmap/phase-10-domain-intelligence.md",
        }
    )
    v7_validator = "scripts/audit/validate-phase-10.34-v7-evidence.py"
    if (REPO_ROOT / v7_validator).is_file():
        required_paths.add(v7_validator)
    for relative in sorted(required_paths):
        destination = archive_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, destination)
    _rebind_fixture_evidence(archive_root)
    return archive_root


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rebind_fixture_evidence(archive_root: Path) -> None:
    evidence_dir = archive_root / "docs/audits/evidence"
    manifest_path = evidence_dir / "phase-10.34-v7-source-hashes.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    helper = "tests/domains/domain_session_audit_evidence.py"
    manifest["files"][helper] = _sha256(archive_root / helper)
    v7_validator = "scripts/audit/validate-phase-10.34-v7-evidence.py"
    if (archive_root / v7_validator).is_file():
        manifest["files"][v7_validator] = _sha256(archive_root / v7_validator)
    _write_json(manifest_path, manifest)

    binding = _sha256(manifest_path)
    gates_path = evidence_dir / "phase-10.34-v7-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["source_evidence"]["manifest_sha256"] = binding
    for gate in gates["gates"].values():
        gate["source_hash_manifest_sha256"] = binding
    for group in gates["gate_groups"].values():
        group["source_hash_manifest_sha256"] = binding
    gates["pre_audit"]["source_hash_manifest_sha256"] = binding
    _write_json(gates_path, gates)


def _write_audit(
    archive_root: Path,
    version: int,
    *,
    status: str,
    blockers: int,
    majors: int,
    minors: int,
) -> None:
    path = archive_root / f"docs/audits/phase-10.34-independent-audit-v{version}.md"
    path.write_text(
        "\n".join(
            (
                f"FINAL_INDEPENDENT_AUDIT_V{version}={status}",
                f"BLOCKERS={blockers}",
                f"MAJORS={majors}",
                f"MINORS={minors}",
                "",
            )
        ),
        encoding="utf-8",
    )


def _write_audit_text(archive_root: Path, version: int, text: str) -> None:
    path = archive_root / f"docs/audits/phase-10.34-independent-audit-v{version}.md"
    path.write_text(text, encoding="utf-8")


def _set_phase_status(archive_root: Path, status: str) -> None:
    for relative in (
        "docs/roadmap/phase-10-domain-intelligence.md",
        "docs/reference/domain-sessions.md",
    ):
        path = archive_root / relative
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace("`IMPLEMENTED_PENDING_AUDIT`", f"`{status}`", 1),
            encoding="utf-8",
        )


def test_01_current_v6_fail_is_valid_evidence_but_not_closure_eligible(
    tmp_path: Path,
) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    closure = report.resolved[56].details
    assert report.evidence_resolved == 56
    assert closure["latest_independent_audit"] == "V6"
    assert closure["latest_independent_audit_status"] == "FAIL"
    assert closure["closure_eligible"] is False


def test_02_simulated_v7_clean_pass_keeps_validator_valid_and_allows_closure(
    tmp_path: Path,
) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(
        archive_root,
        7,
        status="PASS",
        blockers=0,
        majors=0,
        minors=0,
    )

    report = validate_at_dp_034_bundle_evidence(archive_root)

    assert report.evidence_resolved == 56
    closure = report.resolved[56].details
    assert closure["latest_independent_audit"] == "V7"
    assert closure["latest_independent_audit_status"] == "PASS"
    assert closure["closure_eligible"] is True


def test_03_simulated_v7_fail_is_valid_evidence_but_not_closure_eligible(
    tmp_path: Path,
) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(
        archive_root,
        7,
        status="FAIL",
        blockers=0,
        majors=1,
        minors=0,
    )

    report = validate_at_dp_034_bundle_evidence(archive_root)

    assert report.evidence_resolved == 56
    closure = report.resolved[56].details
    assert closure["latest_independent_audit"] == "V7"
    assert closure["latest_independent_audit_status"] == "FAIL"
    assert closure["closure_eligible"] is False


@pytest.mark.parametrize(
    ("blockers", "majors", "minors"),
    [(0, 1, 0), (1, 0, 0), (0, 0, 1)],
    ids=("04-majors", "05-blockers", "06-minors"),
)
def test_pass_with_nonzero_finding_fails_closed(
    tmp_path: Path,
    blockers: int,
    majors: int,
    minors: int,
) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(
        archive_root,
        7,
        status="PASS",
        blockers=blockers,
        majors=majors,
        minors=minors,
    )

    with pytest.raises(EvidenceValidationError, match="PASS requires zero findings"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_07_malformed_audit_marker_fails_closed(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit_text(
        archive_root,
        7,
        "FINAL_INDEPENDENT_AUDIT_V7=MAYBE\nBLOCKERS=0\nMAJORS=0\nMINORS=0\n",
    )

    with pytest.raises(EvidenceValidationError, match="FINAL marker is malformed"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_08_missing_finding_counts_fail_closed(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit_text(
        archive_root,
        7,
        "FINAL_INDEPENDENT_AUDIT_V7=FAIL\nBLOCKERS=0\nMAJORS=1\n",
    )

    with pytest.raises(EvidenceValidationError, match="missing MINORS"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_09_duplicate_final_marker_fails_closed(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit_text(
        archive_root,
        7,
        (
            "FINAL_INDEPENDENT_AUDIT_V7=FAIL\n"
            "FINAL_INDEPENDENT_AUDIT_V7=FAIL\n"
            "BLOCKERS=0\nMAJORS=1\nMINORS=0\n"
        ),
    )

    with pytest.raises(EvidenceValidationError, match="duplicate FINAL marker"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_10_filename_and_marker_version_mismatch_fails_closed(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit_text(
        archive_root,
        7,
        "FINAL_INDEPENDENT_AUDIT_V6=FAIL\nBLOCKERS=0\nMAJORS=1\nMINORS=0\n",
    )

    with pytest.raises(EvidenceValidationError, match="version mismatch"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_11_audit_v10_is_selected_over_v9_numerically(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(archive_root, 9, status="FAIL", blockers=0, majors=2, minors=0)
    _write_audit(archive_root, 10, status="FAIL", blockers=0, majors=1, minors=0)

    audit = discover_latest_independent_audit(archive_root)

    assert audit is not None
    assert audit.version == 10
    assert audit.majors == 1


def test_12_premature_complete_roadmap_with_latest_fail_fails_closed(
    tmp_path: Path,
) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _set_phase_status(archive_root, "COMPLETE")

    with pytest.raises(EvidenceValidationError, match="closed without a clean"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_13_post_pass_pending_roadmap_is_valid_transitional_state(
    tmp_path: Path,
) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(archive_root, 7, status="PASS", blockers=0, majors=0, minors=0)

    result = evaluate_phase_10_34_closure_eligibility(archive_root)

    assert result.phase_status == "IMPLEMENTED_PENDING_AUDIT"
    assert result.closure_eligible is True


def test_14_post_pass_portable_validator_remains_56_of_56(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    _write_audit(archive_root, 7, status="PASS", blockers=0, majors=0, minors=0)
    validator = archive_root / "scripts/audit/validate-phase-10.34-v7-evidence.py"

    completed = subprocess.run(
        (sys.executable, str(validator), str(archive_root)),
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "AT_DP_034_PORTABLE_VALIDATION=PASS" in completed.stdout
    assert "EVIDENCE_RESOLVED=56/56" in completed.stdout
    assert "CLOSURE_ELIGIBLE=YES" in completed.stdout


def test_15_source_hash_validation_still_rejects_mutation(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    source = archive_root / "cmm/domains/session_resumer.py"
    source.write_text(source.read_text(encoding="utf-8") + "\n# mutation\n")

    with pytest.raises(EvidenceValidationError, match="source hash mismatch"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_16_external_gate_mutation_still_fails(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    gates_path = archive_root / "docs/audits/evidence/phase-10.34-v7-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["gates"]["focused_tests"]["status"] = "FAIL"
    _write_json(gates_path, gates)

    with pytest.raises(EvidenceValidationError, match="focused_tests must be PASS"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_17_pytest_inventory_mutation_still_fails(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    inventory_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v7-pytest-nodes.txt"
    )
    nodes = inventory_path.read_text(encoding="utf-8").splitlines()
    inventory_path.write_text("\n".join(nodes[1:]) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="inventory hash mismatch"):
        validate_at_dp_034_bundle_evidence(archive_root)
