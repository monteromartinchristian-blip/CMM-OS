"""Phase 10.34 — Domain Sessions — Independent Audit V4 regressions."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.composition_contracts import DomainCompositionInput
from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainResolutionStatus, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.knowledge_authority import DefaultDomainKnowledgeAuthority
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.resolver_contracts import DomainResolutionResult
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
    EVIDENCE_MANIFEST_PATH,
    EXTERNAL_GATES_PATH,
    EvidenceValidationError,
    collect_pytest_nodes,
    validate_at_dp_034,
)
from tests.domains.domain_session_test_support import shared_session_adapter

NOW = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _definition(slug: str) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version="1.0.0",
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version="1.0.0"),
        operations=(f"op:{slug}:read",),
        permissions=(f"perm:{slug}:read",),
    )


def _registry(
    *, health_active: bool = True, fitness_active: bool = True
) -> DomainRegistry:
    registry = DomainRegistry()
    for slug, active in (("health", health_active), ("fitness", fitness_active)):
        definition = _definition(slug)
        registry.register(definition)
        registry.restore_record(
            DomainRegistryRecord(
                definition=definition,
                status=DomainStatus.ACTIVE if active else DomainStatus.DISABLED,
                registered_at=NOW,
                updated_at=NOW,
            )
        )
    return registry


def _resumer(
    registry: DomainRegistry,
    **overrides: object,
) -> DomainSessionResumer:
    kwargs: dict[str, object] = {
        "registry": registry,
        "permission_evaluator": lambda _actor, permissions: permissions,
        "operation_filter": lambda _permissions, operations: operations,
        "shared_session_adapter": shared_session_adapter(),
    }
    kwargs.update(overrides)
    return DomainSessionResumer(**kwargs)


def _resource_authority(
    resource_id: str,
    *,
    valid_until: datetime,
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
            historical_allowed=False,
        ),
    )
    return DefaultDomainResourceAuthority(
        resources={resource_id: context},
        definitions={resource_id: definition},
    )


def test_01_recomposition_does_not_synthesize_domain_resolution_result() -> None:
    """Removing a supporting domain must call recompose with session-state input."""

    class SpyComposer:
        def __init__(self) -> None:
            self.recomposition_input: DomainCompositionInput | None = None

        def compose(self, resolution: object, definitions: object) -> object:
            raise AssertionError(
                f"synthetic resolver authority received: {resolution!r}"
            )

        def recompose(
            self,
            composition_input: DomainCompositionInput,
            definitions: object,
        ) -> object:
            self.recomposition_input = composition_input
            return DefaultDomainComposer().recompose(composition_input, definitions)

    composer = SpyComposer()
    result = _resumer(_registry(fitness_active=False), composer=composer).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-no-synthetic", temporal_reference=NOW
        ),
        DomainSessionContext(
            session_id="audit-v4-no-synthetic",
            primary_domain="domain:health",
            supporting_domains=("domain:fitness",),
            composition_id="composition:historic",
            last_resolution_id="resolution:historic",
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert composer.recomposition_input is not None
    assert composer.recomposition_input.resolution_authoritative is False
    assert composer.recomposition_input.previous_resolution_id == "resolution:historic"


def test_02_genuine_canonical_resolution_result_is_preserved_exactly() -> None:
    """A canonical re-resolution object must reach composition and lineage unchanged."""
    real_resolution = DomainResolutionResult(
        id="resolution:canonical:42",
        context_id="resolution-context:42",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId("health"),
        confidence=0.87,
        resolved_at=NOW,
        metadata={"authority": "canonical-resolver"},
    )

    class Resolver:
        def resolve(self, _context: object) -> DomainResolutionResult:
            return real_resolution

    class SpyComposer:
        seen: DomainResolutionResult | None = None

        def compose(
            self,
            resolution: DomainResolutionResult,
            definitions: object,
        ) -> object:
            self.seen = resolution
            return DefaultDomainComposer().compose(resolution, definitions)

    composer = SpyComposer()
    result = _resumer(
        _registry(fitness_active=False), resolver=Resolver(), composer=composer
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-real-resolution", temporal_reference=NOW
        ),
        DomainSessionContext(
            session_id="audit-v4-real-resolution",
            primary_domain="domain:fitness",
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert composer.seen is real_resolution
    assert result.context is not None
    assert result.context.last_resolution_id == real_resolution.id
    assert result.context.domain_transitions[-1].resolution_id == real_resolution.id


def test_03_real_expired_native_resource_blocks_resume() -> None:
    """The repository-native temporal policy must reject an expired resource."""
    resource_id = "res:expired"
    result = _resumer(
        _registry(),
        resource_authority=_resource_authority(
            resource_id, valid_until=NOW - timedelta(hours=1)
        ),
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-expired-native",
            temporal_reference=NOW,
            current_resource_versions={resource_id: "v1"},
        ),
        DomainSessionContext(
            session_id="audit-v4-expired-native",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            updated_at=NOW,
        ),
    )

    assert result.status in {
        DomainSessionResumeStatus.BLOCKED,
        DomainSessionResumeStatus.INCOMPATIBLE,
        DomainSessionResumeStatus.REPLAN_REQUIRED,
    }
    resource_check = next(
        c for c in result.checks if c.name == f"resource_drift_{resource_id}"
    )
    assert resource_check.status is not DomainSessionCheckStatus.PASS
    assert result.recorded_resumption is False


def test_04_valid_native_resource_passes() -> None:
    """A currently valid native resource can resume when its authority passes it."""
    resource_id = "res:current"
    result = _resumer(
        _registry(),
        resource_authority=_resource_authority(
            resource_id, valid_until=NOW + timedelta(hours=1)
        ),
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-current-native", temporal_reference=NOW
        ),
        DomainSessionContext(
            session_id="audit-v4-current-native",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            updated_at=NOW,
        ),
    )

    resource_check = next(
        c for c in result.checks if c.name == f"resource_drift_{resource_id}"
    )
    assert resource_check.status is DomainSessionCheckStatus.PASS
    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.recorded_resumption is True


def test_05_missing_resource_authority_fails_conservative() -> None:
    """A version snapshot cannot stand in for missing current resource authority."""
    resource_id = "res:unverified"
    result = _resumer(_registry()).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-missing-resource-authority",
            temporal_reference=NOW,
            current_resource_versions={resource_id: "v1"},
        ),
        DomainSessionContext(
            session_id="audit-v4-missing-resource-authority",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert any(c.blocking and resource_id in c.name for c in result.checks)


def test_06_missing_knowledge_authority_fails_conservative() -> None:
    """A version snapshot cannot stand in for missing current knowledge authority."""
    knowledge_id = "know:unverified"
    result = _resumer(_registry()).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-missing-knowledge-authority",
            temporal_reference=NOW,
            current_knowledge_versions={knowledge_id: "v1"},
        ),
        DomainSessionContext(
            session_id="audit-v4-missing-knowledge-authority",
            primary_domain="domain:health",
            domain_knowledge_refs={"domain:health": (knowledge_id,)},
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert any(c.blocking and knowledge_id in c.name for c in result.checks)


def test_07_version_string_cannot_override_native_expiration() -> None:
    """Native expiration outranks a request snapshot that claims the same version."""
    resource_id = "res:expired-same-version"
    result = _resumer(
        _registry(),
        resource_authority=_resource_authority(
            resource_id, valid_until=NOW - timedelta(seconds=1)
        ),
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-version-vs-native",
            temporal_reference=NOW,
            current_resource_versions={resource_id: "v1"},
        ),
        DomainSessionContext(
            session_id="audit-v4-version-vs-native",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert any("historical use" in c.message for c in result.checks)


def test_08_native_resource_drift_invalidates_continuity() -> None:
    """A native staleness verdict must force replanning and clear derived refs."""
    resource_id = "res:stale-window"
    result = _resumer(
        _registry(),
        resource_authority=_resource_authority(
            resource_id,
            valid_until=NOW + timedelta(hours=1),
            last_verified_at=NOW - timedelta(minutes=5),
            validity_window_seconds=60,
        ),
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-native-resource-drift", temporal_reference=NOW
        ),
        DomainSessionContext(
            session_id="audit-v4-native-resource-drift",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            partial_result_refs=("partial:stale-resource",),
            trace_refs=("trace:stale-resource",),
            next_recommended_step="continue_stale_resource",
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.REPLAN_REQUIRED
    assert result.context is not None
    assert result.context.partial_result_refs == ()
    assert result.context.trace_refs == ()
    assert result.context.next_recommended_step == "replan_execution"


def test_09_native_knowledge_invalidation_invalidates_continuity() -> None:
    """Authoritative knowledge invalidation must prevent stale continuation."""
    knowledge_id = "know:invalidated"
    authority = DefaultDomainKnowledgeAuthority({knowledge_id: "INVALIDATED"})
    result = _resumer(_registry(), knowledge_authority=authority).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-native-knowledge-invalid", temporal_reference=NOW
        ),
        DomainSessionContext(
            session_id="audit-v4-native-knowledge-invalid",
            primary_domain="domain:health",
            domain_knowledge_refs={"domain:health": (knowledge_id,)},
            partial_result_refs=("partial:invalid-knowledge",),
            trace_refs=("trace:invalid-knowledge",),
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.context is None
    assert result.recorded_resumption is False
    assert any(c.blocking and knowledge_id in c.name for c in result.checks)


def test_missing_temporal_reference_uses_current_clock_for_native_freshness() -> None:
    """Native freshness must use current truth, not the persisted update timestamp."""
    resource_id = "res:expired-after-persistence"
    result = _resumer(
        _registry(),
        resource_authority=_resource_authority(
            resource_id, valid_until=NOW + timedelta(hours=1)
        ),
        clock=lambda: NOW + timedelta(hours=2),
    ).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-current-clock-native-freshness"
        ),
        DomainSessionContext(
            session_id="audit-v4-current-clock-native-freshness",
            primary_domain="domain:health",
            domain_resource_refs={"domain:health": (resource_id,)},
            updated_at=NOW,
        ),
    )

    resource_check = next(
        c for c in result.checks if c.name == f"resource_drift_{resource_id}"
    )
    assert resource_check.status is not DomainSessionCheckStatus.PASS
    assert resource_check.blocking is True
    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False


def test_canonical_reresolution_empty_support_replaces_historical_support() -> None:
    """Canonical empty support is authoritative and must clear historical support."""
    resolution = DomainResolutionResult(
        id="resolution:canonical:no-support",
        context_id="resolution-context:no-support",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId("health"),
        supporting_domains=(),
        confidence=0.91,
        resolved_at=NOW,
    )

    class Resolver:
        def resolve(self, _context: object) -> DomainResolutionResult:
            return resolution

    result = _resumer(_registry(fitness_active=False), resolver=Resolver()).resume(
        DomainSessionResumeRequest(
            session_id="audit-v4-reresolution-clears-support",
            temporal_reference=NOW,
        ),
        DomainSessionContext(
            session_id="audit-v4-reresolution-clears-support",
            primary_domain="domain:fitness",
            supporting_domains=("domain:health",),
            updated_at=NOW,
        ),
    )

    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert result.context is not None
    assert result.context.primary_domain == "domain:health"
    assert result.context.supporting_domains == ()
    assert result.context.last_resolution_id == resolution.id


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _evidence_copies(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, object], dict[str, object]]:
    manifest = _load_json(EVIDENCE_MANIFEST_PATH)
    gates = _load_json(EXTERNAL_GATES_PATH)
    manifest_path = tmp_path / "manifest.json"
    gates_path = tmp_path / "gates.json"
    _write_json(manifest_path, manifest)
    _write_json(gates_path, gates)
    return manifest_path, gates_path, manifest, gates


def _validate_copies(
    manifest_path: Path,
    gates_path: Path,
) -> object:
    return validate_at_dp_034(
        manifest_path=manifest_path,
        gates_path=gates_path,
        collected_nodes=collect_pytest_nodes(),
    )


def test_10_at_dp_manifest_has_exactly_56_unique_checkpoints() -> None:
    report = validate_at_dp_034()
    assert report.logical_checkpoints == 56
    assert tuple(report.resolved) == tuple(range(1, 57))


def test_11_all_required_checkpoints_carry_resolved_evidence() -> None:
    report = validate_at_dp_034()
    assert report.required_checkpoints == 56
    assert report.evidence_resolved == 56
    assert report.placeholders == 0


def test_12_pytest_evidence_references_resolve_to_collected_nodes() -> None:
    report = validate_at_dp_034()
    pytest_evidence = [
        item for item in report.resolved.values() if item.evidence_type == "pytest_node"
    ]
    assert len(pytest_evidence) == 47
    assert all(
        item.evidence_reference in report.collected_pytest_nodes
        for item in pytest_evidence
    )


def test_13_missing_evidence_reference_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"][0]["evidence_reference"] = ""
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="evidence_reference"):
        _validate_copies(manifest_path, gates_path)


def test_14_failed_external_gate_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, _manifest, gates = _evidence_copies(tmp_path)
    gates["gates"]["focused_tests"]["status"] = "FAIL"
    _write_json(gates_path, gates)
    with pytest.raises(EvidenceValidationError, match="focused_tests.*PASS"):
        _validate_copies(manifest_path, gates_path)


def test_15_wrong_source_manifest_digest_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, _manifest, gates = _evidence_copies(tmp_path)
    gates["source_evidence"]["manifest_sha256"] = "0" * 64
    _write_json(gates_path, gates)
    with pytest.raises(EvidenceValidationError, match="manifest digest mismatch"):
        _validate_copies(manifest_path, gates_path)


def test_16_duplicate_checkpoint_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"].append(deepcopy(manifest["checkpoints"][0]))
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="duplicate checkpoint"):
        _validate_copies(manifest_path, gates_path)


def test_17_nonexistent_pytest_node_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"][0]["evidence_reference"] = (
        "tests/domains/test_domain_session_acceptance.py::test_does_not_exist"
    )
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="pytest node does not exist"):
        _validate_copies(manifest_path, gates_path)


def test_18_checkpoint_48_binds_focused_gate() -> None:
    evidence = validate_at_dp_034().resolved[48]
    assert (evidence.evidence_type, evidence.evidence_reference) == (
        "external_gate",
        "focused_tests",
    )
    assert evidence.actual_count > 0


def test_19_checkpoint_49_binds_domain_gate() -> None:
    evidence = validate_at_dp_034().resolved[49]
    assert (evidence.evidence_type, evidence.evidence_reference) == (
        "external_gate",
        "domain_tests",
    )
    assert evidence.actual_count > 0


def test_20_checkpoint_50_binds_global_gate() -> None:
    evidence = validate_at_dp_034().resolved[50]
    assert (evidence.evidence_type, evidence.evidence_reference) == (
        "external_gate",
        "global_tests",
    )
    assert evidence.actual_count > 0


def test_21_checkpoint_51_binds_real_quality_gates() -> None:
    evidence = validate_at_dp_034().resolved[51]
    assert evidence.evidence_reference == "quality_gates"
    assert evidence.component_gates == (
        "ruff_check",
        "ruff_format",
        "compileall",
        "diff_check",
    )


def test_22_checkpoint_53_binds_phase_10_33_regression() -> None:
    evidence = validate_at_dp_034().resolved[53]
    assert evidence.evidence_reference == "phase10_33_regression"
    assert evidence.details["general_event_count"] == 23
    assert evidence.details["general_event_unique_count"] == 23
    assert evidence.details["domain_session_resumed_event"] == "ABSENT"


def test_23_checkpoint_54_validates_bundle_generation_contract() -> None:
    evidence = validate_at_dp_034().resolved[54]
    assert evidence.evidence_type == "artifact_contract"
    assert evidence.details["prefix"] == "CMM-OS-phase-10.34/"
    assert evidence.details["pax_commit_id_verification"] is True
    assert evidence.details["forbidden_paths_check"] is True


def test_24_checkpoint_55_validates_actual_pre_audit_gates() -> None:
    evidence = validate_at_dp_034().resolved[55]
    assert evidence.evidence_reference == "pre_audit_gates"
    assert evidence.details["worktree_clean_when_generated"] is True
    assert evidence.details["all_required_external_gates_pass"] is True


def test_25_checkpoint_56_enforces_closure_guard() -> None:
    evidence = validate_at_dp_034().resolved[56]
    assert evidence.evidence_type == "documentation_gate"
    details = evidence.details
    assert details["latest_independent_audit"].startswith("V")
    assert details["latest_independent_audit_status"] in {"PASS", "FAIL"}
    clean_pass = details["latest_independent_audit_status"] == "PASS" and not any(
        details[name] for name in ("blockers", "majors", "minors")
    )
    assert details["closure_eligible"] is clean_pass


def test_26_invalid_evidence_type_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"][0]["evidence_type"] = "manual"
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="invalid evidence_type"):
        _validate_copies(manifest_path, gates_path)


def test_27_missing_manifest_is_rejected(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing-manifest.json"
    with pytest.raises(EvidenceValidationError, match="manifest.*missing"):
        validate_at_dp_034(
            manifest_path=missing_manifest,
            collected_nodes=collect_pytest_nodes(),
        )


def test_28_missing_external_gate_artifact_is_rejected(tmp_path: Path) -> None:
    missing_gates = tmp_path / "missing-gates.json"
    with pytest.raises(EvidenceValidationError, match="gate artifact.*missing"):
        validate_at_dp_034(
            gates_path=missing_gates,
            collected_nodes=collect_pytest_nodes(),
        )


def test_29_placeholder_evidence_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"][0]["evidence_reference"] = "placeholder"
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="placeholder"):
        _validate_copies(manifest_path, gates_path)


def test_30_self_asserted_pass_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, _manifest, gates = _evidence_copies(tmp_path)
    gates["gates"]["focused_tests"]["result_source"] = "self_asserted"
    _write_json(gates_path, gates)
    with pytest.raises(EvidenceValidationError, match="self.asserted"):
        _validate_copies(manifest_path, gates_path)


def test_31_external_gate_without_real_command_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, _manifest, gates = _evidence_copies(tmp_path)
    gates["gates"]["global_tests"]["command"] = ""
    _write_json(gates_path, gates)
    with pytest.raises(EvidenceValidationError, match="global_tests.*command"):
        _validate_copies(manifest_path, gates_path)


def test_32_missing_checkpoint_is_rejected(tmp_path: Path) -> None:
    manifest_path, gates_path, manifest, _gates = _evidence_copies(tmp_path)
    manifest["checkpoints"] = manifest["checkpoints"][:-1]
    _write_json(manifest_path, manifest)
    with pytest.raises(EvidenceValidationError, match="IDs 1..56"):
        _validate_copies(manifest_path, gates_path)
