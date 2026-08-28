"""Phase 10.32 independent audit V1 regression tests.

These tests encode findings B1, M1, M2, M3 and m1 from the independent
audit of phase-10.32-audit-v1.tar.gz.

They are intentionally added before production remediation and must be
observed RED on audited HEAD fd26501.
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId


def _ref(
    source_id: str,
    *,
    domain: str | None = None,
    blocking: bool = False,
    authority: DomainConflictAuthority = DomainConflictAuthority.PRIMARY_DOMAIN,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug=domain) if domain is not None else None,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


# ---------------------------------------------------------------------------
# B1 — aggregate blocking state must not hide a blocking source reference
# ---------------------------------------------------------------------------


def test_audit_v1_b1_case_rejects_nonblocking_aggregate_with_blocking_reference() -> (
    None
):
    blocking_ref = _ref(
        "blocking-ref",
        domain="project",
        blocking=True,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-b1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.DOMAIN_PRECEDENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(blocking_ref,),
            blocking=False,
        )


# ---------------------------------------------------------------------------
# M1 — primary-domain precedence must never resolve knowledge truth conflicts
# ---------------------------------------------------------------------------


def test_audit_v1_m1_primary_precedence_cannot_resolve_knowledge_conflict() -> None:
    project = DomainId(slug="project")
    general = DomainId(slug="general")
    case = DomainConflictCase(
        id="case-m1",
        domains=(project, general),
        kind=DomainConflictKind.KNOWLEDGE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("project-claim", domain="project"),
            _ref("general-claim", domain="general"),
        ),
        blocking=False,
    )

    result = DomainConflictResolver().resolve(case, primary_domain=project)

    assert result.status is DomainConflictStatus.UNRESOLVED
    assert result.can_proceed is False
    assert result.conflict_preserved is True
    assert result.winning_reference_ids == ()
    assert DomainConflictReasonCode.STRATEGY_NOT_APPLICABLE in result.reason_codes


# ---------------------------------------------------------------------------
# M2 — resolution contracts must reject semantically contradictory states
# ---------------------------------------------------------------------------


def test_audit_v1_m2_maintain_conflict_cannot_claim_resolved_or_proceed() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-m2-maintain",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.PRESERVED,),
            conflict_preserved=True,
            can_proceed=True,
        )


def test_audit_v1_m2_separate_results_cannot_claim_semantic_resolution() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-m2-separate",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            preserved_reference_ids=("ref-1", "ref-2"),
            reason_codes=(DomainConflictReasonCode.SEPARATE_RESULTS,),
            conflict_preserved=True,
            can_proceed=True,
        )


def test_audit_v1_m2_rejected_reference_requires_auditable_reason_code() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-m2-rejected",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            winning_reference_ids=("winner",),
            rejected_reference_ids=("loser",),
            reason_codes=(),
            conflict_preserved=False,
            can_proceed=True,
        )


# ---------------------------------------------------------------------------
# M3 — MappingProxyType inputs must still be deeply copied/frozen
# ---------------------------------------------------------------------------


def _nested_proxy() -> tuple[dict[str, object], MappingProxyType[str, object]]:
    nested: dict[str, object] = {"flag": True}
    return nested, MappingProxyType({"nested": nested})


def test_audit_v1_m3_reference_mappingproxy_is_deeply_frozen() -> None:
    nested, metadata = _nested_proxy()
    obj = DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="m3-reference",
        metadata=metadata,
    )

    nested["flag"] = False

    assert obj.metadata["nested"]["flag"] is True


def test_audit_v1_m3_case_mappingproxy_is_deeply_frozen() -> None:
    nested, metadata = _nested_proxy()
    obj = DomainConflictCase(
        id="m3-case",
        domains=(),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_ref("m3-case-ref"),),
        metadata=metadata,
    )

    nested["flag"] = False

    assert obj.metadata["nested"]["flag"] is True


def test_audit_v1_m3_resolution_mappingproxy_is_deeply_frozen() -> None:
    nested, metadata = _nested_proxy()
    obj = DomainConflictResolution(
        conflict_id="m3-resolution",
        status=DomainConflictStatus.UNRESOLVED,
        strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.PRESERVED,),
        conflict_preserved=True,
        can_proceed=False,
        metadata=metadata,
    )

    nested["flag"] = False

    assert obj.metadata["nested"]["flag"] is True


def test_audit_v1_m3_policy_mappingproxy_is_deeply_frozen() -> None:
    nested, metadata = _nested_proxy()
    obj = DomainConflictResolutionPolicy(metadata=metadata)

    nested["flag"] = False

    assert obj.metadata["nested"]["flag"] is True


# ---------------------------------------------------------------------------
# m1 — malformed serialized inputs must raise the typed serialization error
# ---------------------------------------------------------------------------


def test_audit_v1_minor1_reference_missing_required_field_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_id": "missing-source-kind",
                "blocking": False,
            }
        )


def test_audit_v1_minor1_case_missing_required_field_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(
            {
                "id": "missing-kind",
                "domains": [],
                "severity": "material",
                "status": "open",
                "references": [
                    {
                        "source_kind": "domain_specific_conflict",
                        "source_id": "ref-1",
                        "blocking": False,
                    }
                ],
                "blocking": False,
            }
        )


def test_audit_v1_minor1_resolution_missing_required_field_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolution.from_dict(
            {
                "conflict_id": "missing-status",
                "strategy": "maintain_conflict",
                "preserved_reference_ids": ["ref-1"],
                "reason_codes": ["DOMAIN_CONFLICT_PRESERVED"],
                "conflict_preserved": True,
                "can_proceed": False,
            }
        )
