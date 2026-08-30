"""Machine-verifiable AT-DP-034 evidence validation for Phase 10.34."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_MANIFEST_PATH = (
    REPO_ROOT / "docs/audits/evidence/phase-10.34-at-dp-034-manifest.json"
)
EXTERNAL_GATES_PATH = REPO_ROOT / "docs/audits/evidence/phase-10.34-v5-gates.json"

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
    evidence_commit: str
    resolved: Mapping[int, ResolvedEvidence]
    collected_pytest_nodes: frozenset[str]


def _fail(message: str) -> None:
    raise EvidenceValidationError(message)


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        _fail(f"{label} missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _fail(f"{label} is not readable JSON: {exc}")
    if not isinstance(payload, dict):
        _fail(f"{label} must contain a JSON object")
    return payload


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )


def _validate_canonical_artifacts_committed(
    repo_root: Path,
    manifest_path: Path,
    gates_path: Path,
) -> str:
    """Bind canonical evidence bytes to the current commit without self-reference."""
    canonical_paths = (EVIDENCE_MANIFEST_PATH.resolve(), EXTERNAL_GATES_PATH.resolve())
    supplied_paths = (manifest_path.resolve(), gates_path.resolve())
    if supplied_paths != canonical_paths:
        return "fixture"

    relative_paths = tuple(str(path.relative_to(repo_root)) for path in canonical_paths)
    tracked = _run_git(repo_root, "ls-files", "--error-unmatch", "--", *relative_paths)
    if tracked.returncode != 0:
        _fail("canonical evidence artifacts must be tracked by Git")

    clean = _run_git(repo_root, "diff", "--quiet", "HEAD", "--", *relative_paths)
    if clean.returncode != 0:
        _fail("canonical evidence artifacts must match their committed bytes")

    head = _run_git(repo_root, "rev-parse", "HEAD")
    evidence_commit = head.stdout.strip()
    if head.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", evidence_commit):
        _fail("current evidence commit cannot be resolved")
    return evidence_commit


@lru_cache(maxsize=4)
def _collect_pytest_nodes_cached(repo_root_text: str) -> frozenset[str]:
    repo_root = Path(repo_root_text)
    python = repo_root / ".venv/bin/python"
    completed = subprocess.run(
        (str(python), "-m", "pytest", "--collect-only", "-q"),
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


def _validate_verified_tree(gates: Mapping[str, Any], repo_root: Path) -> str:
    commit = gates.get("verified_source_commit")
    verified_tree = gates.get("verified_source_tree")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        _fail("gate artifact verified_source_commit must be a full Git SHA")
    if not isinstance(verified_tree, str) or not re.fullmatch(
        r"[0-9a-f]{40}", verified_tree
    ):
        _fail("gate artifact verified_source_tree must be a full Git tree SHA")

    tree_result = _run_git(repo_root, "rev-parse", f"{commit}^{{tree}}")
    if tree_result.returncode != 0:
        _fail(f"verified_source_commit cannot be resolved: {commit}")
    actual_tree = tree_result.stdout.strip()
    if actual_tree != verified_tree:
        _fail(
            "verified_source_tree does not match verified_source_commit: "
            f"expected {actual_tree}, recorded {verified_tree}"
        )

    diff_result = _run_git(
        repo_root,
        "diff",
        "--quiet",
        commit,
        "--",
        "cmm",
        "tests",
        "pyproject.toml",
    )
    if diff_result.returncode != 0:
        _fail(
            "current source/test tree differs from the tree bound to external evidence"
        )
    return verified_tree


def _validate_gate_record(
    gate_id: str,
    gate: Any,
    verified_tree: str,
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
    if gate.get("verified_source_tree") != verified_tree:
        _fail(f"external gate {gate_id} has wrong verified_source_tree")
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
    verified_tree: str,
) -> dict[str, Mapping[str, Any]]:
    raw_gates = gates_payload.get("gates")
    if not isinstance(raw_gates, Mapping):
        _fail("gate artifact gates must be an object")
    validated: dict[str, Mapping[str, Any]] = {}
    for gate_id in REQUIRED_GATE_IDS:
        validated[gate_id] = _validate_gate_record(
            gate_id, raw_gates.get(gate_id), verified_tree
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
    verified_tree: str,
) -> ResolvedEvidence:
    raw_groups = gates_payload.get("gate_groups")
    if not isinstance(raw_groups, Mapping):
        _fail("gate artifact gate_groups must be an object")
    group = raw_groups.get(reference)
    if not isinstance(group, Mapping):
        _fail(f"external gate group {reference} is missing")
    if group.get("status") != "PASS":
        _fail(f"external gate group {reference} must be PASS")
    if group.get("verified_source_tree") != verified_tree:
        _fail(f"external gate group {reference} has wrong verified_source_tree")
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
        if pre_audit.get("worktree_clean_when_generated") is not True:
            _fail("pre_audit evidence must record a clean worktree")
        if pre_audit.get("verified_source_tree") != verified_tree:
            _fail("pre_audit evidence has wrong verified_source_tree")
        details = {
            "worktree_clean_when_generated": True,
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
    if contract.get("forbidden_paths_check") is not True:
        _fail("artifact contract must verify forbidden archive paths")
    forbidden = contract.get("forbidden_member_patterns")
    required_forbidden = (".git", ".venv", "__pycache__", ".pyc")
    if not isinstance(forbidden, list) or tuple(forbidden) != required_forbidden:
        _fail("artifact contract has an incomplete forbidden paths check")
    return contract


def _validate_closure_guard(repo_root: Path) -> Mapping[str, Any]:
    audit_dir = repo_root / "docs/audits"
    audits: list[tuple[int, Path]] = []
    pattern = re.compile(r"phase-10\.34-independent-audit-v(\d+)\.md$")
    for path in audit_dir.glob("phase-10.34-independent-audit-v*.md"):
        match = pattern.search(path.name)
        if match:
            audits.append((int(match.group(1)), path))
    if not audits:
        _fail("closure guard found no independent Phase 10.34 audit")
    latest_version, latest_path = max(audits)
    latest_text = latest_path.read_text(encoding="utf-8")
    if latest_version != 4 or "FINAL_INDEPENDENT_AUDIT_V4=FAIL" not in latest_text:
        _fail("closure guard requires latest independent audit V4 FAIL")

    roadmap_text = (repo_root / "ROADMAP.md").read_text(encoding="utf-8")
    if "IMPLEMENTED_PENDING_AUDIT" not in roadmap_text:
        _fail("closure guard requires IMPLEMENTED_PENDING_AUDIT")
    if "independent re-audit V5 pending" not in roadmap_text:
        _fail("closure guard requires independent re-audit V5 pending")
    if (audit_dir / "phase-10.34-independent-audit-v5.md").exists():
        _fail("closure guard forbids a self-authored independent audit V5")
    return MappingProxyType(
        {
            "latest_independent_audit": "V4",
            "latest_independent_audit_status": "FAIL",
            "phase_status": "IMPLEMENTED_PENDING_AUDIT",
        }
    )


def validate_at_dp_034(
    *,
    repo_root: Path = REPO_ROOT,
    manifest_path: Path = EVIDENCE_MANIFEST_PATH,
    gates_path: Path = EXTERNAL_GATES_PATH,
    collected_nodes: frozenset[str] | None = None,
) -> EvidenceValidationReport:
    """Validate every required AT-DP-034 checkpoint against real evidence."""
    manifest = _read_json(manifest_path, label="evidence manifest")
    gates_payload = _read_json(gates_path, label="external gate artifact")
    evidence_commit = _validate_canonical_artifacts_committed(
        repo_root, manifest_path, gates_path
    )
    checkpoints = _validate_manifest_shape(manifest)
    nodes = (
        collected_nodes
        if collected_nodes is not None
        else collect_pytest_nodes(repo_root)
    )
    verified_tree = _validate_verified_tree(gates_payload, repo_root)
    validated_gates = _validate_external_gates(gates_payload, verified_tree)

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
                    reference, gates_payload, validated_gates, verified_tree
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
        verified_source_tree=verified_tree,
        evidence_commit=evidence_commit,
        resolved=MappingProxyType(resolved),
        collected_pytest_nodes=frozenset(nodes),
    )


__all__ = [
    "EVIDENCE_MANIFEST_PATH",
    "EXTERNAL_GATES_PATH",
    "EvidenceValidationError",
    "EvidenceValidationReport",
    "ResolvedEvidence",
    "collect_pytest_nodes",
    "validate_at_dp_034",
]
