"""Phase 10.34 — Domain Sessions — Independent Audit V5 regressions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import KnowledgeKind, KnowledgeStatus, TemporalScopeKind
from cmm.cognitive.knowledge import KnowledgeItem, TemporalScope
from cmm.cognitive.store_memory import InMemoryKnowledgeStore
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.knowledge_authority import DefaultDomainKnowledgeAuthority
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resource_authority import DefaultDomainResourceAuthority
from cmm.domains.resource_contracts import (
    DomainResourceContext,
    DomainResourceDefinition,
    DomainResourceTemporalPolicy,
)
from cmm.domains.session_contracts import (
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from tests.domains.domain_session_audit_evidence import (
    EvidenceValidationError,
    validate_at_dp_034_bundle_evidence,
)
from tests.domains.domain_session_lifecycle_test_support import (
    PENDING,
    copy_real_audit,
    portable_archive_fixture,
)
from tests.domains.domain_session_test_support import shared_session_adapter

NOW = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]


def _resource_authority(
    resource_id: str,
    *,
    valid_until: datetime,
    historical_allowed: bool,
    last_verified_at: datetime | None = None,
    validity_window_seconds: int | None = None,
) -> DefaultDomainResourceAuthority:
    temporal_scope: dict[str, datetime] = {"valid_until": valid_until}
    if last_verified_at is not None:
        temporal_scope["last_verified_at"] = last_verified_at
    context = DomainResourceContext(
        resource_id=resource_id,
        kind="clinical-record",
        provenance=("native:clinical-system",),
        temporal_scope=temporal_scope,
    )
    definition = DomainResourceDefinition(
        id=f"definition:{resource_id}",
        kind="clinical-record",
        domain_id=DomainId("health"),
        adapter="health.clinical_record",
        temporal_policy=DomainResourceTemporalPolicy(
            validity_window_seconds=validity_window_seconds,
            expiration_required=True,
            historical_allowed=historical_allowed,
        ),
    )
    return DefaultDomainResourceAuthority(
        resources={resource_id: context},
        definitions={resource_id: definition},
    )


def _knowledge_item(
    knowledge_id: str,
    *,
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE,
    temporal_scope: TemporalScope | None = None,
) -> KnowledgeItem:
    kwargs: dict[str, object] = {}
    if status is KnowledgeStatus.INVALIDATED:
        kwargs.update(
            invalidated_at=NOW,
            invalidation_reason="native invalidation",
        )
    elif status is KnowledgeStatus.SUPERSEDED:
        kwargs["superseded_by_id"] = f"{knowledge_id}:revision"
    return KnowledgeItem(
        id=knowledge_id,
        statement=f"Canonical knowledge {knowledge_id}",
        kind=KnowledgeKind.FACT,
        confidence=Confidence(0.95),
        status=status,
        temporal_scope=temporal_scope or TemporalScope(kind=TemporalScopeKind.TIMELESS),
        created_at=NOW,
        updated_at=NOW,
        **kwargs,
    )


def _authority_with_item(item: KnowledgeItem) -> DefaultDomainKnowledgeAuthority:
    store = InMemoryKnowledgeStore()
    store.save_item(item)
    return DefaultDomainKnowledgeAuthority(store=store)


def _registry() -> DomainRegistry:
    definition = DomainDefinition(
        id=DomainId("health"),
        name="health",
        display_name="Health",
        version="1.0.0",
        kind=DomainKind.PERSONAL,
        description="Health domain",
        manifest_id=DomainManifestId(slug="health", version="1.0.0"),
        operations=("op:health:read",),
        permissions=("perm:health:read",),
    )
    registry = DomainRegistry()
    registry.register(definition)
    registry.restore_record(
        DomainRegistryRecord(
            definition=definition,
            status=DomainStatus.ACTIVE,
            registered_at=NOW,
            updated_at=NOW,
        )
    )
    return registry


def _resumer(authority: DefaultDomainKnowledgeAuthority) -> DomainSessionResumer:
    return DomainSessionResumer(
        registry=_registry(),
        permission_evaluator=lambda _actor, permissions: permissions,
        operation_filter=lambda _permissions, operations: operations,
        knowledge_authority=authority,
        shared_session_adapter=shared_session_adapter(),
    )


def test_01_native_resource_historical_allowed_policy_is_preserved() -> None:
    verdict = _resource_authority(
        "res:historical-allowed",
        valid_until=NOW - timedelta(hours=1),
        historical_allowed=True,
    ).resolve_resource_freshness("res:historical-allowed", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_02_native_resource_historical_disallowed_is_blocked() -> None:
    verdict = _resource_authority(
        "res:historical-blocked",
        valid_until=NOW - timedelta(hours=1),
        historical_allowed=False,
    ).resolve_resource_freshness("res:historical-blocked", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_03_valid_native_resource_passes() -> None:
    verdict = _resource_authority(
        "res:current",
        valid_until=NOW + timedelta(hours=1),
        historical_allowed=False,
    ).resolve_resource_freshness("res:current", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_native_resource_stale_window_uses_canonical_drift() -> None:
    verdict = _resource_authority(
        "res:stale-window",
        valid_until=NOW + timedelta(hours=1),
        historical_allowed=False,
        last_verified_at=NOW - timedelta(minutes=5),
        validity_window_seconds=60,
    ).resolve_resource_freshness("res:stale-window", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.DRIFT
    assert verdict.is_blocking is False


def test_04_canonical_knowledge_item_invalidated_is_blocked() -> None:
    item = _knowledge_item("know:invalidated", status=KnowledgeStatus.INVALIDATED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True
    assert verdict.details["status"] == KnowledgeStatus.INVALIDATED.value


def test_05_canonical_knowledge_item_superseded_is_blocked() -> None:
    item = _knowledge_item("know:superseded", status=KnowledgeStatus.SUPERSEDED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True
    assert verdict.details["superseded_by_id"] == "know:superseded:revision"


def test_06_canonical_knowledge_item_active_and_temporally_valid_is_current() -> None:
    item = _knowledge_item("know:active")
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is False


def test_07_canonical_knowledge_item_unverified_is_conservative() -> None:
    item = _knowledge_item("know:unverified", status=KnowledgeStatus.UNVERIFIED)
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is not DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is True


def test_08_missing_canonical_knowledge_fails_closed() -> None:
    verdict = DefaultDomainKnowledgeAuthority(
        store=InMemoryKnowledgeStore()
    ).resolve_knowledge_freshness("know:missing", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_native_knowledge_temporal_invalidity_is_conservative() -> None:
    item = _knowledge_item(
        "know:expired",
        temporal_scope=TemporalScope(
            kind=TemporalScopeKind.INTERVAL,
            valid_from=NOW - timedelta(days=2),
            valid_until=NOW - timedelta(days=1),
        ),
    )
    verdict = _authority_with_item(item).resolve_knowledge_freshness(item.id, at=NOW)

    assert verdict.status is not DomainSessionCheckStatus.PASS
    assert verdict.is_blocking is True


def test_unknown_mapping_object_is_not_assumed_current() -> None:
    verdict = DefaultDomainKnowledgeAuthority(
        {"know:unknown": object()}
    ).resolve_knowledge_freshness("know:unknown", at=NOW)

    assert verdict.status is DomainSessionCheckStatus.BLOCKING
    assert verdict.is_blocking is True


def test_09_session_e2e_invalidated_knowledge_cannot_resume() -> None:
    item = _knowledge_item(
        "know:session-invalidated", status=KnowledgeStatus.INVALIDATED
    )
    result = _resumer(_authority_with_item(item)).resume(
        DomainSessionResumeRequest(
            session_id="audit-v5-native-invalidated",
            temporal_reference=NOW,
        ),
        DomainSessionContext(
            session_id="audit-v5-native-invalidated",
            primary_domain="domain:health",
            domain_knowledge_refs={"domain:health": (item.id,)},
            updated_at=NOW,
        ),
    )

    knowledge_check = next(
        check for check in result.checks if check.name == f"knowledge_drift_{item.id}"
    )
    assert knowledge_check.status is DomainSessionCheckStatus.BLOCKING
    assert knowledge_check.blocking is True
    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False


def _portable_archive_fixture(tmp_path: Path) -> Path:
    archive_root = portable_archive_fixture(
        tmp_path,
        status=PENDING,
        pending_audit_version=9,
    )
    copy_real_audit(REPO_ROOT, archive_root, 6)
    assert not (archive_root / ".git").exists()
    assert not (archive_root / ".venv").exists()
    return archive_root


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _rebind_source_manifest(archive_root: Path) -> None:
    manifest_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    )
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    gates_path = archive_root / "docs/audits/evidence/phase-10.34-v10-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["source_evidence"]["manifest_sha256"] = digest
    for gate in gates["gates"].values():
        gate["source_hash_manifest_sha256"] = digest
    for group in gates["gate_groups"].values():
        group["source_hash_manifest_sha256"] = digest
    gates["pre_audit"]["source_hash_manifest_sha256"] = digest
    _write_json(gates_path, gates)


def test_10_portable_evidence_validator_succeeds_without_git(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)

    report = validate_at_dp_034_bundle_evidence(archive_root)

    assert report.evidence_resolved == 56


def test_11_portable_evidence_validator_succeeds_without_venv(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)

    report = validate_at_dp_034_bundle_evidence(archive_root)

    assert report.logical_checkpoints == 56
    assert len(report.collected_pytest_nodes) > 0


def test_12_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    source = archive_root / "cmm/domains/resource_authority.py"
    source.write_text(source.read_text(encoding="utf-8") + "\n# mutation\n")

    with pytest.raises(EvidenceValidationError, match="hash mismatch"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_13_missing_hashed_source_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    (archive_root / "cmm/domains/resource_authority.py").unlink()

    with pytest.raises(EvidenceValidationError, match="missing"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_14_gate_fail_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    gates_path = archive_root / "docs/audits/evidence/phase-10.34-v10-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["gates"]["focused_tests"]["status"] = "FAIL"
    _write_json(gates_path, gates)

    with pytest.raises(EvidenceValidationError, match="focused_tests.*PASS"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_15_pytest_inventory_mutation_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    inventory_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-pytest-nodes.txt"
    )
    nodes = inventory_path.read_text(encoding="utf-8").splitlines()
    inventory_path.write_text("\n".join(nodes[1:]) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="inventory.*hash"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_16_missing_evidence_artifact_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    (archive_root / "docs/audits/evidence/phase-10.34-v10-gates.json").unlink()

    with pytest.raises(EvidenceValidationError, match="gate artifact.*missing"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_17_fifty_six_unique_checkpoints_still_resolve(tmp_path: Path) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    assert report.logical_checkpoints == 56
    assert report.required_checkpoints == 56
    assert tuple(report.resolved) == tuple(range(1, 57))


@pytest.mark.parametrize(
    ("checkpoint_id", "evidence_reference"),
    [
        (48, "focused_tests"),
        (49, "domain_tests"),
        (50, "global_tests"),
        (53, "phase10_33_regression"),
    ],
)
def test_portable_counted_checkpoint_evidence(
    tmp_path: Path,
    checkpoint_id: int,
    evidence_reference: str,
) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    evidence = report.resolved[checkpoint_id]
    assert evidence.evidence_reference == evidence_reference
    assert evidence.actual_count is not None
    assert evidence.actual_count > 0


def test_21_checkpoint_51_portable_quality_evidence(tmp_path: Path) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    assert report.resolved[51].component_gates == (
        "ruff_check",
        "ruff_format",
        "compileall",
        "diff_check",
    )


def test_23_checkpoint_54_archive_contract_is_portable(tmp_path: Path) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    contract = report.resolved[54].details
    assert contract["generator"] == "git archive"
    assert contract["prefix"] == "CMM-OS-phase-10.34/"
    assert contract["pax_commit_id_verification"] is True


def test_24_checkpoint_55_pre_audit_gate_is_portable(tmp_path: Path) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    assert report.resolved[55].details["all_required_external_gates_pass"] is True


def test_25_checkpoint_56_closure_guard_is_portable(tmp_path: Path) -> None:
    report = validate_at_dp_034_bundle_evidence(_portable_archive_fixture(tmp_path))

    closure = report.resolved[56].details
    assert closure["latest_independent_audit"] == "V6"
    assert closure["latest_independent_audit_status"] == "FAIL"
    assert closure["phase_status"] == "IMPLEMENTED_PENDING_AUDIT"
    assert closure["closure_eligible"] is False


def test_unknown_source_hash_algorithm_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    manifest_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["algorithm"] = "md5"
    _write_json(manifest_path, manifest)
    _rebind_source_manifest(archive_root)

    with pytest.raises(EvidenceValidationError, match="unknown algorithm"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_source_hash_path_traversal_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    manifest_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["../escape.py"] = "0" * 64
    _write_json(manifest_path, manifest)
    _rebind_source_manifest(archive_root)

    with pytest.raises(EvidenceValidationError, match="path traversal"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_duplicate_source_hash_path_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    manifest_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    )
    manifest_path.write_text(
        '{"algorithm":"sha256","files":{"same.py":"'
        + "0" * 64
        + '","same.py":"'
        + "0" * 64
        + '"},"schema_version":1}\n',
        encoding="utf-8",
    )
    _rebind_source_manifest(archive_root)

    with pytest.raises(EvidenceValidationError, match="duplicate key"):
        validate_at_dp_034_bundle_evidence(archive_root)


def test_required_source_absent_from_manifest_is_rejected(tmp_path: Path) -> None:
    archive_root = _portable_archive_fixture(tmp_path)
    manifest_path = (
        archive_root / "docs/audits/evidence/phase-10.34-v10-source-hashes.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["files"]["cmm/domains/resource_authority.py"]
    _write_json(manifest_path, manifest)
    _rebind_source_manifest(archive_root)

    with pytest.raises(EvidenceValidationError, match="absent from hash manifest"):
        validate_at_dp_034_bundle_evidence(archive_root)
