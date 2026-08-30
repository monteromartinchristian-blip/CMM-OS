"""State-explicit portable fixtures for Phase 10.34 lifecycle tests."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PENDING = "IMPLEMENTED_PENDING_AUDIT"
COMPLETE = "COMPLETE"
EVIDENCE_VERSION = 10


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise AssertionError(
            f"fixture marker not found exactly once: {path}: {pattern}"
        )
    path.write_text(updated, encoding="utf-8")


def _set_main_roadmap_state(
    archive_root: Path,
    *,
    status: str,
    pending_audit_version: int | None,
) -> None:
    path = archive_root / "ROADMAP.md"
    if status == PENDING:
        assert pending_audit_version is not None
        implemented = (
            "> **Implemented:** Phases 0–9 plus Phase 10 through 10.34 "
            f"(Phase 10.34 independent re-audit V{pending_audit_version} pending)<br>"
        )
        progress = (
            "**Current progress:** Phase 10.19–10.33 are complete and independently "
            "audited. Phase 10.34 — Domain Sessions is implemented with "
            "`DP-034=IMPLEMENTED`, `AT-DP-034=IMPLEMENTED_PENDING_AUDIT`; "
            f"independent re-audit V{pending_audit_version} pending. Phase 10.35 — "
            "Domain SDK is next after a clean independent audit."
        )
        implemented_through = (
            "**Implemented through:** Phase 10.34 — Domain Sessions "
            f"(`IMPLEMENTED_PENDING_AUDIT`; independent re-audit "
            f"V{pending_audit_version} pending)."
        )
        narrative = (
            "remains closed. Phase 10.33 is independently audited and closed; "
            "Phase 10.34 is implemented pending independent audit, and the remaining "
            "implementation sequence is 10.35 → 10.53, with 10.52–10.53 as the "
            "final planned Domain Packs."
        )
    else:
        implemented = (
            "> **Implemented:** Phases 0–9 plus Phase 10 through 10.34 "
            "(Phase 10.34 complete; final independent audit V10 `PASS`)<br>"
        )
        progress = (
            "**Current progress:** Phase 10.19–10.34 are complete and independently "
            "audited. Phase 10.34 — Domain Sessions has `DP-034=VERIFIED_EXISTING` "
            "and `AT-DP-034=PASS`; final independent audit V10 `PASS`. Phase 10.35 — "
            "Domain SDK is next."
        )
        implemented_through = (
            "**Implemented through:** Phase 10.34 — Domain Sessions "
            "(`COMPLETE`; final independent audit V10 `PASS`; "
            "`DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS`)."
        )
        narrative = (
            "remains closed. Phase 10.33 and Phase 10.34 are independently audited "
            "and closed; the remaining implementation sequence is 10.35 → 10.53, "
            "with 10.52–10.53 as the final planned Domain Packs."
        )
    _replace_once(path, r"^> \*\*Implemented:\*\*.*$", implemented)
    _replace_once(path, r"^\*\*Current progress:\*\*.*$", progress)
    _replace_once(path, r"^\*\*Implemented through:\*\*.*$", implemented_through)
    _replace_once(
        path,
        r"^remains closed\. Phases? 10\.33.*final planned Domain Packs\.$",
        narrative,
    )


def _set_requirements_matrix_state(
    archive_root: Path,
    *,
    status: str,
    pending_audit_version: int | None,
) -> None:
    path = archive_root / "docs/reference/domain-intelligence-requirements-matrix.md"
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    status_index = next(
        index for index, line in enumerate(lines) if line.startswith("**Status:**")
    )
    dp_index = next(
        index for index, line in enumerate(lines) if line.startswith("| `DP-034` |")
    )
    order_index = next(
        index
        for index, line in enumerate(lines)
        if line.startswith("10.34 — Domain Sessions")
    )
    if status == PENDING:
        assert pending_audit_version is not None
        lines[status_index] = (
            "**Status:** Canonical reference for consolidated Phase 10 requirements. "
            "Phase 10.33 is complete and independently audited. Phase 10.34 is "
            f"`IMPLEMENTED_PENDING_AUDIT` with independent re-audit "
            f"V{pending_audit_version} pending. Phase 10.35–10.51 proceed afterward."
        )
        lines[dp_index] = re.sub(
            r"\| `(IMPLEMENTED_PENDING_AUDIT|VERIFIED_EXISTING)` \| "
            r"`AT-DP-034` — `(IMPLEMENTED_PENDING_AUDIT|PASS)`",
            "| `IMPLEMENTED_PENDING_AUDIT` | `AT-DP-034` — `IMPLEMENTED_PENDING_AUDIT`",
            lines[dp_index],
        )
        lines[dp_index] = re.sub(
            r"(?:(?:independent|fixture-isolation) re-audit V\d+ pending|"
            r"final independent audit V\d+ `PASS`)",
            f"independent re-audit V{pending_audit_version} pending",
            lines[dp_index],
        )
        lines[order_index] = (
            "10.34 — Domain Sessions (`IMPLEMENTED_PENDING_AUDIT`; independent "
            f"re-audit V{pending_audit_version} pending)"
        )
    else:
        lines[status_index] = (
            "**Status:** Canonical reference for consolidated Phase 10 requirements. "
            "Phase 10.33 and Phase 10.34 are complete and independently audited; "
            "Phase 10.34 final independent audit V10 `PASS`. Phase 10.35–10.51 "
            "proceed afterward."
        )
        lines[dp_index] = re.sub(
            r"\| `(IMPLEMENTED_PENDING_AUDIT|VERIFIED_EXISTING)` \| "
            r"`AT-DP-034` — `(IMPLEMENTED_PENDING_AUDIT|PASS)`",
            "| `VERIFIED_EXISTING` | `AT-DP-034` — `PASS`",
            lines[dp_index],
        )
        lines[dp_index] = re.sub(
            r"(?:(?:independent|fixture-isolation) re-audit V\d+ pending|"
            r"final independent audit V\d+ `PASS`)",
            "final independent audit V10 `PASS`",
            lines[dp_index],
        )
        lines[order_index] = (
            "10.34 — Domain Sessions (`COMPLETE`; final independent audit V10 `PASS`; "
            "`DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS`)"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_phase_10_34_documented_state(
    archive_root: Path,
    *,
    status: str,
    pending_audit_version: int | None = None,
) -> None:
    """Set Phase 10.34 lifecycle docs in a temporary archive explicitly."""
    if status not in {PENDING, COMPLETE}:
        raise ValueError(f"unsupported Phase 10.34 fixture status: {status}")
    if status == PENDING and pending_audit_version is None:
        raise ValueError("pending_audit_version is required for pending fixtures")
    if status == COMPLETE and pending_audit_version is not None:
        raise ValueError("complete fixtures cannot carry pending_audit_version")

    _set_main_roadmap_state(
        archive_root,
        status=status,
        pending_audit_version=pending_audit_version,
    )
    phase_roadmap = archive_root / "docs/roadmap/phase-10-domain-intelligence.md"
    reference = archive_root / "docs/reference/domain-sessions.md"
    if status == PENDING:
        phase_line = (
            f"> **Status:** `{PENDING}`; independent re-audit "
            f"V{pending_audit_version} pending"
        )
        reference_line = (
            f"**Status:** `{PENDING}`; independent re-audit "
            f"V{pending_audit_version} pending (Phase 10.34)"
        )
    else:
        phase_line = (
            "> **Status:** `COMPLETE`; final independent audit V10 `PASS`; "
            "`DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS`"
        )
        reference_line = (
            "**Status:** `COMPLETE`; final independent audit V10 `PASS`; "
            "`DP-034=VERIFIED_EXISTING`; `AT-DP-034=PASS` (Phase 10.34)"
        )
    phase_text = phase_roadmap.read_text(encoding="utf-8")
    phase_start = phase_text.index("10.34 - Domain Sessions")
    phase_prefix = phase_text[:phase_start]
    phase_section = phase_text[phase_start:]
    phase_section, count = re.subn(
        r"^> \*\*Status:\*\*.*$", phase_line, phase_section, count=1, flags=re.MULTILINE
    )
    if count != 1:
        raise AssertionError("Phase 10.34 detailed roadmap status marker missing")
    phase_roadmap.write_text(phase_prefix + phase_section, encoding="utf-8")
    _replace_once(reference, r"^\*\*Status:\*\*.*$", reference_line)
    _set_requirements_matrix_state(
        archive_root,
        status=status,
        pending_audit_version=pending_audit_version,
    )


def _rebind_fixture_evidence(archive_root: Path) -> None:
    evidence_dir = archive_root / "docs/audits/evidence"
    manifest_path = evidence_dir / (
        f"phase-10.34-v{EVIDENCE_VERSION}-source-hashes.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in manifest["files"]:
        manifest["files"][relative] = _sha256(archive_root / relative)
    _write_json(manifest_path, manifest)

    binding = _sha256(manifest_path)
    gates_path = evidence_dir / f"phase-10.34-v{EVIDENCE_VERSION}-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["source_evidence"]["manifest_sha256"] = binding
    for gate in gates["gates"].values():
        gate["source_hash_manifest_sha256"] = binding
    for group in gates["gate_groups"].values():
        group["source_hash_manifest_sha256"] = binding
    gates["pre_audit"]["source_hash_manifest_sha256"] = binding
    _write_json(gates_path, gates)


def portable_archive_fixture(
    tmp_path: Path,
    *,
    status: str,
    pending_audit_version: int | None = None,
    source_root: Path = REPO_ROOT,
) -> Path:
    """Copy a portable candidate and force the requested lifecycle doc state."""
    archive_root = tmp_path / "CMM-OS-phase-10.34"
    evidence_dir = "docs/audits/evidence"
    source_manifest_path = source_root / (
        f"{evidence_dir}/phase-10.34-v{EVIDENCE_VERSION}-source-hashes.json"
    )
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    required_paths = set(source_manifest["files"])
    required_paths.update(
        {
            "ROADMAP.md",
            f"{evidence_dir}/phase-10.34-at-dp-034-manifest.json",
            f"{evidence_dir}/phase-10.34-v{EVIDENCE_VERSION}-gates.json",
            f"{evidence_dir}/phase-10.34-v{EVIDENCE_VERSION}-pytest-nodes.txt",
            f"{evidence_dir}/phase-10.34-v{EVIDENCE_VERSION}-source-hashes.json",
            "docs/reference/domain-intelligence-requirements-matrix.md",
            "docs/reference/domain-sessions.md",
            "docs/roadmap/phase-10-domain-intelligence.md",
        }
    )
    validator = f"scripts/audit/validate-phase-10.34-v{EVIDENCE_VERSION}-evidence.py"
    if (source_root / validator).is_file():
        required_paths.add(validator)
    for relative in sorted(required_paths):
        destination = archive_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, destination)
    _rebind_fixture_evidence(archive_root)
    set_phase_10_34_documented_state(
        archive_root,
        status=status,
        pending_audit_version=pending_audit_version,
    )
    return archive_root


def write_audit(
    archive_root: Path,
    version: int,
    *,
    status: str,
    blockers: int,
    majors: int,
    minors: int,
    audited_source_hash_manifest_sha256: str | None = None,
) -> None:
    if status == "PASS" and audited_source_hash_manifest_sha256 is None:
        manifest_path = archive_root / (
            f"docs/audits/evidence/phase-10.34-v{EVIDENCE_VERSION}-source-hashes.json"
        )
        audited_source_hash_manifest_sha256 = _sha256(manifest_path)
    audit_lines = [
        f"FINAL_INDEPENDENT_AUDIT_V{version}={status}",
        f"BLOCKERS={blockers}",
        f"MAJORS={majors}",
        f"MINORS={minors}",
    ]
    if audited_source_hash_manifest_sha256 is not None:
        audit_lines.append(
            f"AUDITED_SOURCE_HASH_MANIFEST_SHA256={audited_source_hash_manifest_sha256}"
        )
    path = archive_root / f"docs/audits/phase-10.34-independent-audit-v{version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join((*audit_lines, "")),
        encoding="utf-8",
    )


def write_audit_text(archive_root: Path, version: int, text: str) -> None:
    path = archive_root / f"docs/audits/phase-10.34-independent-audit-v{version}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_real_audit(source_root: Path, archive_root: Path, version: int) -> None:
    source = source_root / f"docs/audits/phase-10.34-independent-audit-v{version}.md"
    destination = archive_root / source.relative_to(source_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


__all__ = [
    "COMPLETE",
    "PENDING",
    "REPO_ROOT",
    "_write_json",
    "copy_real_audit",
    "portable_archive_fixture",
    "set_phase_10_34_documented_state",
    "write_audit",
    "write_audit_text",
]
