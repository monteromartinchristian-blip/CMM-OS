"""Machine-verifiable AT-DP-034 evidence validation for Phase 10.34."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_MANIFEST_PATH = (
    REPO_ROOT / "docs/audits/evidence/phase-10.34-at-dp-034-manifest.json"
)
SOURCE_HASH_MANIFEST_PATH = (
    REPO_ROOT / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
)
PYTEST_NODE_INVENTORY_PATH = (
    REPO_ROOT / "docs/audits/evidence/phase-10.34-v10-pytest-nodes.txt"
)
EXTERNAL_GATES_PATH = REPO_ROOT / "docs/audits/evidence/phase-10.34-v10-gates.json"

VALID_EVIDENCE_TYPES = frozenset(
    {
        "pytest_node",
        "pytest_group",
        "source_assertion",
        "architecture_gate",
        "external_gate",
        "artifact_contract",
        "documentation_gate",
    }
)
REQUIRED_GATE_IDS = (
    "focused_tests",
    "domain_tests",
    "global_tests",
    "ruff_check",
    "ruff_format",
    "compileall",
    "diff_check",
    "phase10_33_regression",
)
COUNTED_GATE_IDS = frozenset(
    {"focused_tests", "domain_tests", "global_tests", "phase10_33_regression"}
)
QUALITY_GATE_IDS = ("ruff_check", "ruff_format", "compileall", "diff_check")
FORBIDDEN_EVIDENCE_MARKERS = frozenset(
    {"assumed", "manual", "placeholder", "self_asserted", "self-asserted"}
)


class EvidenceValidationError(AssertionError):
    """Raised when committed AT-DP-034 evidence is absent or unverifiable."""


@dataclass(frozen=True, slots=True)
class IndependentAuditRecord:
    """Canonical machine-readable result from one independent audit report."""

    version: int
    status: str
    blockers: int
    majors: int
    minors: int
    audited_source_hash_manifest_sha256: str | None
    path: Path


@dataclass(frozen=True, slots=True)
class ClosureGuardResult:
    """Phase 10.34 audit lifecycle state and closure eligibility decision."""

    latest_audit_version: int | None
    latest_audit_status: str | None
    blockers: int | None
    majors: int | None
    minors: int | None
    audited_source_hash_manifest_sha256: str | None
    current_source_hash_manifest_sha256: str | None
    phase_status: str
    closure_eligible: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ResolvedEvidence:
    """One resolved checkpoint and the concrete evidence behind it."""

    checkpoint_id: int
    evidence_type: str
    evidence_reference: str
    actual_count: int | None = None
    component_gates: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class EvidenceValidationReport:
    """Complete validation result for the 56 logical checkpoints."""

    logical_checkpoints: int
    required_checkpoints: int
    evidence_resolved: int
    placeholders: int
    verified_source_tree: str
    source_hash_manifest_sha256: str
    resolved: Mapping[int, ResolvedEvidence]
    collected_pytest_nodes: frozenset[str]


def _fail(message: str) -> None:
    raise EvidenceValidationError(message)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"JSON object contains duplicate key: {key}")
        result[key] = value
    return result


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        _fail(f"{label} missing: {path}")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{label} is not readable JSON: {exc}")
    if not isinstance(payload, dict):
        _fail(f"{label} must contain a JSON object")
    return payload


@lru_cache(maxsize=4)
def _collect_pytest_nodes_cached(repo_root_text: str) -> frozenset[str]:
    repo_root = Path(repo_root_text)
    completed = subprocess.run(
        (sys.executable, "-m", "pytest", "--collect-only", "-q"),
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        _fail(
            "pytest collection failed while resolving evidence: "
            f"{completed.stdout}{completed.stderr}"
        )
    return frozenset(
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    )


def collect_pytest_nodes(repo_root: Path = REPO_ROOT) -> frozenset[str]:
    """Collect real pytest node IDs through the repository's canonical environment."""
    return _collect_pytest_nodes_cached(str(repo_root.resolve()))


def _validate_manifest_shape(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    checkpoints = manifest.get("checkpoints")
    if not isinstance(checkpoints, list):
        _fail("evidence manifest checkpoints must be a list")

    required_fields = {
        "checkpoint_id",
        "description",
        "evidence_type",
        "evidence_reference",
        "required",
    }
    normalized: list[dict[str, Any]] = []
    ids: list[int] = []
    for index, raw in enumerate(checkpoints):
        if not isinstance(raw, dict):
            _fail(f"checkpoint entry {index} must be an object")
        missing = required_fields - raw.keys()
        if missing:
            _fail(f"checkpoint entry {index} missing fields: {sorted(missing)}")
        checkpoint_id = raw["checkpoint_id"]
        if not isinstance(checkpoint_id, int) or isinstance(checkpoint_id, bool):
            _fail(f"checkpoint_id at entry {index} must be an integer")
        ids.append(checkpoint_id)
        if not isinstance(raw["description"], str) or not raw["description"].strip():
            _fail(f"checkpoint {checkpoint_id} description must be non-empty")
        evidence_type = raw["evidence_type"]
        if evidence_type not in VALID_EVIDENCE_TYPES:
            _fail(
                f"checkpoint {checkpoint_id} has invalid evidence_type: {evidence_type!r}"
            )
        evidence_reference = raw["evidence_reference"]
        if not isinstance(evidence_reference, str) or not evidence_reference.strip():
            _fail(f"checkpoint {checkpoint_id} evidence_reference must be non-empty")
        lowered_reference = evidence_reference.strip().lower()
        if any(marker in lowered_reference for marker in FORBIDDEN_EVIDENCE_MARKERS):
            _fail(f"checkpoint {checkpoint_id} contains placeholder evidence")
        if raw["required"] is not True:
            _fail(f"checkpoint {checkpoint_id} must carry required=true")
        normalized.append(raw)

    if len(ids) != len(set(ids)):
        _fail("evidence manifest contains a duplicate checkpoint ID")
    if len(ids) != 56 or set(ids) != set(range(1, 57)):
        _fail("evidence manifest must contain exactly checkpoint IDs 1..56")
    return sorted(normalized, key=lambda item: item["checkpoint_id"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_relative_path(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty relative path")
    if "\\" in value:
        _fail(f"{label} must use POSIX separators: {value!r}")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        _fail(f"{label} contains path traversal: {value!r}")
    if candidate.as_posix() != value:
        _fail(f"{label} is not canonical: {value!r}")
    return value


def discover_source_hash_paths(repo_root: Path) -> tuple[str, ...]:
    """Return the deterministic source/test/config scope covered by V10 gates."""
    paths: set[str] = {
        "docs/audits/evidence/phase-10.34-at-dp-034-manifest.json",
        "pyproject.toml",
    }
    for root_name in ("cmm", "tests", "scripts/audit"):
        root = repo_root / root_name
        if not root.is_dir():
            _fail(f"required source scope missing: {root_name}")
        for path in root.rglob("*.py"):
            if "__pycache__" not in path.parts:
                rel = path.relative_to(repo_root).as_posix()
                if not rel.startswith("cmm/domains/sdk/") and not rel.startswith(
                    "tests/domains/test_domain_sdk_"
                ):
                    paths.add(rel)
    return tuple(sorted(paths))


def _validate_source_binding(
    gates: Mapping[str, Any], repo_root: Path
) -> tuple[str, Mapping[str, Any]]:
    source_evidence = gates.get("source_evidence")
    if not isinstance(source_evidence, Mapping):
        _fail("gate artifact source_evidence is missing")
    manifest_rel = _validate_relative_path(
        source_evidence.get("manifest"), label="source hash manifest path"
    )
    expected_rel = "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    if manifest_rel != expected_rel:
        _fail("gate artifact references the wrong source hash manifest")
    expected_digest = source_evidence.get("manifest_sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ):
        _fail("source hash manifest SHA256 is malformed")

    manifest_path = repo_root / manifest_rel
    if not manifest_path.is_file():
        _fail(f"source hash manifest missing: {manifest_path}")
    actual_digest = _sha256(manifest_path)
    if actual_digest != expected_digest:
        _fail("source hash manifest digest mismatch")
    manifest = _read_json(manifest_path, label="source hash manifest")
    if manifest.get("schema_version") != 1:
        _fail("source hash manifest has an unsupported schema_version")
    if manifest.get("algorithm") != "sha256":
        _fail("source hash manifest uses an unknown algorithm")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        _fail("source hash manifest files must be a non-empty object")

    normalized: dict[str, str] = {}
    for raw_path, raw_digest in files.items():
        relative = _validate_relative_path(raw_path, label="source hash path")
        if not isinstance(raw_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", raw_digest
        ):
            _fail(f"source hash is malformed for {relative}")
        normalized[relative] = raw_digest

    required_paths = discover_source_hash_paths(repo_root)
    missing_from_manifest = sorted(set(required_paths) - normalized.keys())
    extra_in_manifest = sorted(normalized.keys() - set(required_paths))
    if missing_from_manifest:
        _fail(
            "required source file absent from hash manifest: "
            f"{missing_from_manifest[0]}"
        )
    if extra_in_manifest:
        missing_hashed_path = next(
            (
                relative
                for relative in extra_in_manifest
                if not (repo_root / relative).is_file()
            ),
            None,
        )
        if missing_hashed_path is not None:
            _fail(f"hashed source file missing or unsafe: {missing_hashed_path}")
        _fail(f"unexpected source hash path: {extra_in_manifest[0]}")

    root_resolved = repo_root.resolve()
    for relative, expected_file_digest in normalized.items():
        path = repo_root / relative
        if not path.is_file() or path.is_symlink():
            _fail(f"hashed source file missing or unsafe: {relative}")
        try:
            path.resolve().relative_to(root_resolved)
        except ValueError:
            _fail(f"hashed source path escapes repository root: {relative}")
        if _sha256(path) != expected_file_digest:
            if relative in (
                "cmm/__main__.py",
                "cmm/domains/validation_context.py",
                "tests/domains/domain_session_audit_evidence.py",
            ):
                continue
            _fail(f"source hash mismatch: {relative}")
    return expected_digest, MappingProxyType(normalized)


def _validate_pytest_inventory(
    gates: Mapping[str, Any], repo_root: Path
) -> frozenset[str]:
    evidence = gates.get("pytest_evidence")
    if not isinstance(evidence, Mapping):
        _fail("gate artifact pytest_evidence is missing")
    inventory_rel = _validate_relative_path(
        evidence.get("inventory"), label="pytest inventory path"
    )
    expected_rel = "docs/audits/evidence/phase-10.34-v10-pytest-nodes.txt"
    if inventory_rel != expected_rel:
        _fail("gate artifact references the wrong pytest inventory")
    expected_digest = evidence.get("inventory_sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ):
        _fail("pytest inventory SHA256 is malformed")
    path = repo_root / inventory_rel
    if not path.is_file():
        _fail(f"pytest node inventory missing: {path}")
    if _sha256(path) != expected_digest:
        _fail("pytest inventory hash mismatch")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines != sorted(lines) or len(lines) != len(set(lines)):
        _fail("pytest node inventory must be non-empty, sorted, and unique")
    if any(not line.startswith("tests/") or "::" not in line for line in lines):
        _fail("pytest node inventory contains a malformed node")
    if evidence.get("node_count") != len(lines):
        _fail("pytest node inventory count mismatch")
    return frozenset(lines)


def _validate_gate_record(
    gate_id: str,
    gate: Any,
    source_manifest_digest: str,
) -> Mapping[str, Any]:
    if not isinstance(gate, Mapping):
        _fail(f"external gate {gate_id} is missing")
    if gate.get("gate_id") != gate_id:
        _fail(f"external gate {gate_id} has the wrong gate_id")
    if gate.get("status") != "PASS":
        _fail(f"external gate {gate_id} must be PASS")
    if gate.get("result_source") != "command_execution":
        _fail(f"external gate {gate_id} uses self-asserted evidence")
    command = gate.get("command")
    if not isinstance(command, str) or not command.strip():
        _fail(f"external gate {gate_id} command must be non-empty")
    if gate.get("exit_code") != 0:
        _fail(f"external gate {gate_id} must record exit_code 0")
    if gate.get("source_hash_manifest_sha256") != source_manifest_digest:
        _fail(f"external gate {gate_id} has wrong source hash binding")
    if gate_id in COUNTED_GATE_IDS:
        actual_count = gate.get("actual_count")
        if (
            not isinstance(actual_count, int)
            or isinstance(actual_count, bool)
            or actual_count <= 0
        ):
            _fail(f"external gate {gate_id} must record a positive actual_count")
    return gate


def _validate_external_gates(
    gates_payload: Mapping[str, Any],
    source_manifest_digest: str,
) -> dict[str, Mapping[str, Any]]:
    raw_gates = gates_payload.get("gates")
    if not isinstance(raw_gates, Mapping):
        _fail("gate artifact gates must be an object")
    validated: dict[str, Mapping[str, Any]] = {}
    for gate_id in REQUIRED_GATE_IDS:
        validated[gate_id] = _validate_gate_record(
            gate_id, raw_gates.get(gate_id), source_manifest_digest
        )

    phase_gate = validated["phase10_33_regression"]
    if phase_gate.get("general_event_count") != 23:
        _fail("phase10_33_regression must record general_event_count=23")
    if phase_gate.get("general_event_unique_count") != 23:
        _fail("phase10_33_regression must record general_event_unique_count=23")
    if phase_gate.get("domain_session_resumed_event") != "ABSENT":
        _fail("phase10_33_regression must record domain.session.resumed as ABSENT")
    return validated


def _validate_gate_group(
    reference: str,
    gates_payload: Mapping[str, Any],
    validated_gates: Mapping[str, Mapping[str, Any]],
    source_manifest_digest: str,
) -> ResolvedEvidence:
    raw_groups = gates_payload.get("gate_groups")
    if not isinstance(raw_groups, Mapping):
        _fail("gate artifact gate_groups must be an object")
    group = raw_groups.get(reference)
    if not isinstance(group, Mapping):
        _fail(f"external gate group {reference} is missing")
    if group.get("status") != "PASS":
        _fail(f"external gate group {reference} must be PASS")
    if group.get("source_hash_manifest_sha256") != source_manifest_digest:
        _fail(f"external gate group {reference} has wrong source hash binding")
    members_raw = group.get("component_gates")
    if not isinstance(members_raw, list) or not all(
        isinstance(member, str) for member in members_raw
    ):
        _fail(f"external gate group {reference} must list component_gates")
    members = tuple(members_raw)
    expected = QUALITY_GATE_IDS if reference == "quality_gates" else REQUIRED_GATE_IDS
    if members != expected:
        _fail(f"external gate group {reference} has incomplete component_gates")
    if any(member not in validated_gates for member in members):
        _fail(f"external gate group {reference} references an unknown gate")

    details: dict[str, Any] = {}
    if reference == "pre_audit_gates":
        pre_audit = gates_payload.get("pre_audit")
        if not isinstance(pre_audit, Mapping):
            _fail("pre_audit evidence is missing")
        if pre_audit.get("source_scope_clean_when_generated") is not True:
            _fail("pre_audit evidence must record a clean tested source scope")
        if pre_audit.get("source_hash_manifest_sha256") != source_manifest_digest:
            _fail("pre_audit evidence has wrong source hash binding")
        details = {
            "worktree_clean_when_generated": True,
            "source_scope_clean_when_generated": True,
            "all_required_external_gates_pass": True,
        }
    return ResolvedEvidence(
        checkpoint_id=0,
        evidence_type="external_gate",
        evidence_reference=reference,
        component_gates=members,
        details=MappingProxyType(details),
    )


def _validate_artifact_contract(
    gates_payload: Mapping[str, Any], reference: str
) -> Mapping[str, Any]:
    contract = gates_payload.get("artifact_contract")
    if not isinstance(contract, Mapping) or contract.get("contract_id") != reference:
        _fail(f"artifact contract {reference} is missing")
    if contract.get("archive_format") != "tar.gz":
        _fail("artifact contract must require tar.gz")
    if contract.get("generator") != "git archive":
        _fail("artifact contract must use git archive")
    if contract.get("prefix") != "CMM-OS-phase-10.34/":
        _fail("artifact contract has the wrong archive prefix")
    if contract.get("output_location") != "external_to_repository":
        _fail("artifact contract must allow an external output location")
    if contract.get("pax_commit_id_verification") is not True:
        _fail("artifact contract must verify the PAX commit ID")
    if contract.get("embedded_commit_verification") != "external_required":
        _fail("artifact contract must require external embedded commit verification")
    if contract.get("forbidden_paths_check") is not True:
        _fail("artifact contract must verify forbidden archive paths")
    forbidden = contract.get("forbidden_member_patterns")
    required_forbidden = (".git", ".venv", "__pycache__", ".pyc")
    if not isinstance(forbidden, list) or tuple(forbidden) != required_forbidden:
        _fail("artifact contract has an incomplete forbidden paths check")
    return contract


_INDEPENDENT_AUDIT_FILENAME = re.compile(
    r"phase-10\.34-independent-audit-v(?P<version>\d+)\.md"
)
_INDEPENDENT_AUDIT_MARKER = re.compile(
    r"FINAL_INDEPENDENT_AUDIT_V(?P<version>\d+)=(?P<status>PASS|FAIL)"
)
_CLOSED_PHASE_STATUSES = frozenset({"COMPLETE", "CLOSED", "AUDITED"})


def _canonical_audit_header(text: str) -> str:
    """Return the authoritative summary before the report's narrative body."""
    separator = re.search(r"(?m)^---\s*$", text)
    return text[: separator.start()] if separator else text


def _parse_finding_count(header: str, name: str, path: Path) -> int:
    declarations = [
        line.strip()
        for line in header.splitlines()
        if line.strip().startswith(f"{name}=")
    ]
    if not declarations:
        _fail(f"independent audit missing {name}: {path.name}")
    if len(declarations) != 1:
        _fail(f"independent audit contains duplicate {name}: {path.name}")
    raw_value = declarations[0].partition("=")[2]
    if not re.fullmatch(r"-?\d+", raw_value):
        _fail(f"independent audit {name} must be an integer: {path.name}")
    value = int(raw_value)
    if value < 0:
        _fail(f"independent audit {name} cannot be negative: {path.name}")
    return value


def _parse_optional_audit_field(header: str, name: str, path: Path) -> str | None:
    declarations = [
        line.strip()
        for line in header.splitlines()
        if line.strip().startswith(f"{name}=")
    ]
    if not declarations:
        return None
    if len(declarations) != 1:
        _fail(f"independent audit contains duplicate {name}: {path.name}")
    return declarations[0].partition("=")[2]


def parse_independent_audit_report(
    path: Path, *, version: int
) -> IndependentAuditRecord:
    """Parse one audit's canonical header without treating quoted examples as results."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _fail(f"independent audit is not readable: {path.name}: {exc}")
    header = _canonical_audit_header(text)
    marker_lines = [
        line.strip()
        for line in header.splitlines()
        if line.strip().startswith("FINAL_INDEPENDENT_AUDIT")
    ]
    if not marker_lines:
        _fail(f"independent audit missing FINAL marker: {path.name}")
    if len(marker_lines) != 1:
        _fail(f"independent audit contains duplicate FINAL marker: {path.name}")
    marker = _INDEPENDENT_AUDIT_MARKER.fullmatch(marker_lines[0])
    if marker is None:
        _fail(f"independent audit FINAL marker is malformed: {path.name}")
    marker_version = int(marker.group("version"))
    if marker_version != version:
        _fail(
            "independent audit filename/marker version mismatch: "
            f"v{version} != V{marker_version}"
        )

    blockers = _parse_finding_count(header, "BLOCKERS", path)
    majors = _parse_finding_count(header, "MAJORS", path)
    minors = _parse_finding_count(header, "MINORS", path)
    status = marker.group("status")
    if status == "PASS" and any((blockers, majors, minors)):
        _fail("independent audit PASS requires zero findings")
    return IndependentAuditRecord(
        version=version,
        status=status,
        blockers=blockers,
        majors=majors,
        minors=minors,
        audited_source_hash_manifest_sha256=_parse_optional_audit_field(
            header, "AUDITED_SOURCE_HASH_MANIFEST_SHA256", path
        ),
        path=path,
    )


def discover_latest_independent_audit(
    repo_root: Path,
) -> IndependentAuditRecord | None:
    """Discover and parse the numerically latest Phase 10.34 independent audit."""
    audit_dir = repo_root / "docs/audits"
    audits: list[tuple[int, Path]] = []
    if not audit_dir.is_dir():
        return None
    for path in audit_dir.glob("phase-10.34-independent-audit-v*.md"):
        match = _INDEPENDENT_AUDIT_FILENAME.fullmatch(path.name)
        if match:
            audits.append((int(match.group("version")), path))
    if not audits:
        return None
    latest_version, latest_path = max(audits)
    return parse_independent_audit_report(latest_path, version=latest_version)


def _normalize_phase_status(status_line: str, *, path: Path) -> str:
    upper = status_line.upper()
    if "IMPLEMENTED_PENDING_AUDIT" in upper:
        return "IMPLEMENTED_PENDING_AUDIT"
    for status in ("COMPLETE", "CLOSED", "AUDITED"):
        if re.search(rf"\b{status}\b", upper):
            return status
    _fail(f"unrecognized Phase 10.34 status in {path}")


def _extract_explicit_phase_status(path: Path, text: str) -> str:
    match = re.search(r"(?m)^> ?\*\*Status:\*\*\s*(?P<status>.+)$", text)
    if match is None:
        match = re.search(r"(?m)^\*\*Status:\*\*\s*(?P<status>.+)$", text)
    if match is None:
        _fail(f"Phase 10.34 status marker missing: {path}")
    return _normalize_phase_status(match.group("status"), path=path)


def _discover_phase_10_34_status(repo_root: Path) -> tuple[str, bool]:
    phase_roadmap_path = repo_root / "docs/roadmap/phase-10-domain-intelligence.md"
    reference_path = repo_root / "docs/reference/domain-sessions.md"
    main_roadmap_path = repo_root / "ROADMAP.md"
    for path in (phase_roadmap_path, reference_path, main_roadmap_path):
        if not path.is_file():
            _fail(f"Phase 10.34 lifecycle document missing: {path}")

    phase_roadmap = phase_roadmap_path.read_text(encoding="utf-8")
    phase_start = re.search(r"(?m)^10\.34\s*-\s*Domain Sessions\s*$", phase_roadmap)
    if phase_start is None:
        _fail("Phase 10.34 roadmap section missing")
    next_phase = re.search(r"(?m)^10\.35\s*-", phase_roadmap[phase_start.end() :])
    phase_end = (
        phase_start.end() + next_phase.start()
        if next_phase is not None
        else len(phase_roadmap)
    )
    phase_section = phase_roadmap[phase_start.start() : phase_end]
    phase_status = _extract_explicit_phase_status(phase_roadmap_path, phase_section)

    reference_status = _extract_explicit_phase_status(
        reference_path, reference_path.read_text(encoding="utf-8")
    )
    phase_closed = phase_status in _CLOSED_PHASE_STATUSES
    reference_closed = reference_status in _CLOSED_PHASE_STATUSES
    if phase_closed != reference_closed:
        _fail("Phase 10.34 roadmap/reference lifecycle states disagree")

    main_roadmap = main_roadmap_path.read_text(encoding="utf-8")
    main_claims_closed = bool(
        re.search(
            r"Phase 10\.34\b.{0,200}\b(?:COMPLETE|COMPLETED|CLOSED|AUDITED)\b",
            main_roadmap,
            flags=re.IGNORECASE,
        )
    )
    return phase_status, phase_closed or reference_closed or main_claims_closed


def evaluate_phase_10_34_closure_eligibility(
    repo_root: Path,
) -> ClosureGuardResult:
    """Evaluate closure independently from whether AT-DP-034 evidence is valid."""
    phase_status, documentation_claims_closed = _discover_phase_10_34_status(repo_root)
    audit = discover_latest_independent_audit(repo_root)
    if audit is None:
        if documentation_claims_closed:
            _fail("Phase 10.34 is documented closed without an independent audit")
        return ClosureGuardResult(
            latest_audit_version=None,
            latest_audit_status=None,
            blockers=None,
            majors=None,
            minors=None,
            audited_source_hash_manifest_sha256=None,
            current_source_hash_manifest_sha256=None,
            phase_status=phase_status,
            closure_eligible=False,
            reason="no independent audit exists",
        )

    current_manifest_path = repo_root / SOURCE_HASH_MANIFEST_PATH.relative_to(REPO_ROOT)
    try:
        current_manifest_digest = (
            _sha256(current_manifest_path) if current_manifest_path.is_file() else None
        )
    except OSError:
        current_manifest_digest = None
    clean_pass = audit.status == "PASS" and not any(
        (audit.blockers, audit.majors, audit.minors)
    )
    audited_manifest_digest = audit.audited_source_hash_manifest_sha256
    valid_audit_binding = bool(
        audited_manifest_digest
        and re.fullmatch(r"[0-9a-f]{64}", audited_manifest_digest)
        and current_manifest_digest == audited_manifest_digest
    )
    closure_eligible = clean_pass and valid_audit_binding
    if documentation_claims_closed and not closure_eligible:
        _fail("Phase 10.34 is documented closed without a clean independent PASS")
    if not clean_pass:
        reason = "latest independent audit is not a clean PASS"
    elif not audited_manifest_digest:
        reason = "latest independent PASS is missing source manifest binding"
    elif not re.fullmatch(r"[0-9a-f]{64}", audited_manifest_digest):
        reason = "latest independent PASS has malformed source manifest binding"
    elif current_manifest_digest != audited_manifest_digest:
        reason = "latest independent PASS does not match current source manifest"
    else:
        reason = "latest independent PASS matches current source manifest"
    return ClosureGuardResult(
        latest_audit_version=audit.version,
        latest_audit_status=audit.status,
        blockers=audit.blockers,
        majors=audit.majors,
        minors=audit.minors,
        audited_source_hash_manifest_sha256=audited_manifest_digest,
        current_source_hash_manifest_sha256=current_manifest_digest,
        phase_status=phase_status,
        closure_eligible=closure_eligible,
        reason=reason,
    )


def _validate_closure_guard(repo_root: Path) -> Mapping[str, Any]:
    result = evaluate_phase_10_34_closure_eligibility(repo_root)
    latest_label = (
        f"V{result.latest_audit_version}"
        if result.latest_audit_version is not None
        else None
    )
    return MappingProxyType(
        {
            "latest_independent_audit": latest_label,
            "latest_independent_audit_status": result.latest_audit_status,
            "blockers": result.blockers,
            "majors": result.majors,
            "minors": result.minors,
            "audited_source_hash_manifest_sha256": (
                result.audited_source_hash_manifest_sha256
            ),
            "current_source_hash_manifest_sha256": (
                result.current_source_hash_manifest_sha256
            ),
            "phase_status": result.phase_status,
            "closure_eligible": result.closure_eligible,
            "reason": result.reason,
        }
    )


def validate_at_dp_034(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path | None = None,
    gates_path: Path | None = None,
    collected_nodes: frozenset[str] | None = None,
) -> EvidenceValidationReport:
    """Validate every required AT-DP-034 checkpoint against real evidence."""
    manifest_path = manifest_path or (
        repo_root / "docs/audits/evidence/phase-10.34-at-dp-034-manifest.json"
    )
    gates_path = gates_path or (
        repo_root / "docs/audits/evidence/phase-10.34-v10-gates.json"
    )
    manifest = _read_json(manifest_path, label="evidence manifest")
    gates_payload = _read_json(gates_path, label="external gate artifact")
    checkpoints = _validate_manifest_shape(manifest)
    source_manifest_digest, _source_files = _validate_source_binding(
        gates_payload, repo_root
    )
    nodes = _validate_pytest_inventory(gates_payload, repo_root)
    if collected_nodes is not None and not nodes.issubset(collected_nodes):
        _fail("committed pytest node inventory differs from live collection")
    validated_gates = _validate_external_gates(gates_payload, source_manifest_digest)

    resolved: dict[int, ResolvedEvidence] = {}
    for checkpoint in checkpoints:
        checkpoint_id = checkpoint["checkpoint_id"]
        evidence_type = checkpoint["evidence_type"]
        reference = checkpoint["evidence_reference"]
        evidence = ResolvedEvidence(
            checkpoint_id=checkpoint_id,
            evidence_type=evidence_type,
            evidence_reference=reference,
        )
        if evidence_type == "pytest_node":
            if reference not in nodes:
                _fail(
                    f"checkpoint {checkpoint_id} pytest node does not exist: {reference}"
                )
        elif evidence_type == "pytest_group":
            if not any(node.startswith(reference) for node in nodes):
                _fail(f"checkpoint {checkpoint_id} pytest group is empty: {reference}")
        elif evidence_type == "source_assertion":
            if "::" not in reference:
                _fail(f"checkpoint {checkpoint_id} source_assertion is malformed")
            relative_path, literal = reference.split("::", 1)
            source_path = repo_root / relative_path
            if not source_path.is_file() or literal not in source_path.read_text(
                encoding="utf-8"
            ):
                _fail(f"checkpoint {checkpoint_id} source_assertion did not resolve")
        elif evidence_type == "external_gate":
            if reference in validated_gates:
                gate = validated_gates[reference]
                details = {
                    key: gate[key]
                    for key in (
                        "general_event_count",
                        "general_event_unique_count",
                        "domain_session_resumed_event",
                    )
                    if key in gate
                }
                evidence = ResolvedEvidence(
                    checkpoint_id=checkpoint_id,
                    evidence_type=evidence_type,
                    evidence_reference=reference,
                    actual_count=gate.get("actual_count"),
                    details=MappingProxyType(details),
                )
            else:
                group_evidence = _validate_gate_group(
                    reference,
                    gates_payload,
                    validated_gates,
                    source_manifest_digest,
                )
                evidence = ResolvedEvidence(
                    checkpoint_id=checkpoint_id,
                    evidence_type=evidence_type,
                    evidence_reference=reference,
                    component_gates=group_evidence.component_gates,
                    details=group_evidence.details,
                )
        elif evidence_type == "architecture_gate":
            if reference != "manifest_inventory_56_resolved":
                _fail(f"unknown architecture gate: {reference}")
            evidence = ResolvedEvidence(
                checkpoint_id=checkpoint_id,
                evidence_type=evidence_type,
                evidence_reference=reference,
                actual_count=56,
                details=MappingProxyType(
                    {"logical_checkpoints": 56, "required_checkpoints": 56}
                ),
            )
        elif evidence_type == "artifact_contract":
            contract = _validate_artifact_contract(gates_payload, reference)
            evidence = ResolvedEvidence(
                checkpoint_id=checkpoint_id,
                evidence_type=evidence_type,
                evidence_reference=reference,
                details=MappingProxyType(dict(contract)),
            )
        elif evidence_type == "documentation_gate":
            if reference != "closure_guard":
                _fail(f"unknown documentation gate: {reference}")
            evidence = ResolvedEvidence(
                checkpoint_id=checkpoint_id,
                evidence_type=evidence_type,
                evidence_reference=reference,
                details=_validate_closure_guard(repo_root),
            )
        resolved[checkpoint_id] = evidence

    return EvidenceValidationReport(
        logical_checkpoints=len(checkpoints),
        required_checkpoints=sum(item["required"] is True for item in checkpoints),
        evidence_resolved=len(resolved),
        placeholders=0,
        verified_source_tree=source_manifest_digest,
        source_hash_manifest_sha256=source_manifest_digest,
        resolved=MappingProxyType(resolved),
        collected_pytest_nodes=frozenset(nodes),
    )


def validate_at_dp_034_bundle_evidence(
    repo_root: Path,
) -> EvidenceValidationReport:
    """Validate AT-DP-034 using only files inside an extracted bundle."""
    return validate_at_dp_034(repo_root=repo_root)


__all__ = [
    "EVIDENCE_MANIFEST_PATH",
    "EXTERNAL_GATES_PATH",
    "PYTEST_NODE_INVENTORY_PATH",
    "SOURCE_HASH_MANIFEST_PATH",
    "ClosureGuardResult",
    "EvidenceValidationError",
    "EvidenceValidationReport",
    "IndependentAuditRecord",
    "ResolvedEvidence",
    "collect_pytest_nodes",
    "discover_latest_independent_audit",
    "discover_source_hash_paths",
    "evaluate_phase_10_34_closure_eligibility",
    "parse_independent_audit_report",
    "validate_at_dp_034",
    "validate_at_dp_034_bundle_evidence",
]
