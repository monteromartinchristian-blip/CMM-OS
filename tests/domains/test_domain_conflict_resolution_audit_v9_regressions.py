"""Phase 10.32 independent audit V9 regression tests.

Finding discovered against phase-10.32-audit-v9.tar.gz at:
2cc077dd0af087205e161fda2d640812ff05fadf

These tests must be observed RED before any V9 remediation production change.
"""

from __future__ import annotations

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.identifiers import DomainId

PROJECT = DomainId(slug="project")
GENERAL = DomainId(slug="general")
RESOLVER = DomainConflictResolver()


def _selection_ref(
    *,
    authority: DomainConflictAuthority | None = None,
    domain: DomainId | None = None,
    requires_clarification: bool = True,
    source_id: str = "selection-v9",
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.SELECTION_CONFLICT,
        source_id=source_id,
        domain_id=domain,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=authority,
        metadata={"requires_clarification": requires_clarification},
    )


def _risk_ref() -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id="risk-v9",
        domain_id=PROJECT,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )


def _assert_selection_preserved(
    result,
    *,
    source_id: str = "selection-v9",
) -> None:
    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False
    assert source_id in result.preserved_reference_ids
    assert source_id not in result.rejected_reference_ids


# ---------------------------------------------------------------------------
# M21 — HIGH_RISK_DOMAIN_PRECEDENCE must preserve Phase 10.31 ownership
# ---------------------------------------------------------------------------


def test_audit_v9_m21_selection_source_itself_cannot_be_high_risk_resolved() -> None:
    ref = _selection_ref(
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
        domain=PROJECT,
    )
    case = DomainConflictCase(
        id="selection-direct-high-risk",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.SELECTION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(case, highest_risk_domain=PROJECT)

    _assert_selection_preserved(result)


def test_audit_v9_m21_selection_source_boundary_is_kind_independent() -> None:
    ref = _selection_ref(
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
        domain=PROJECT,
        requires_clarification=False,
    )
    case = DomainConflictCase(
        id="selection-source-kind-boundary",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(case, highest_risk_domain=PROJECT)

    _assert_selection_preserved(result)


def test_audit_v9_m21_high_risk_winner_cannot_reject_selection_ambiguity() -> None:
    selection = _selection_ref()
    risk = _risk_ref()
    case = DomainConflictCase(
        id="mixed-selection-risk",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(selection, risk),
        blocking=False,
    )

    result = RESOLVER.resolve(case, highest_risk_domain=PROJECT)

    _assert_selection_preserved(result)


def test_audit_v9_m21_evidence_policy_cannot_force_high_risk_over_selection() -> None:
    ref = _selection_ref(
        authority=DomainConflictAuthority.EVIDENCE,
        domain=PROJECT,
    )
    case = DomainConflictCase(
        id="selection-evidence-forced-high-risk",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            evidence_strategy=DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
        ),
        highest_risk_domain=PROJECT,
    )

    _assert_selection_preserved(result)


def test_audit_v9_m21_default_policy_cannot_force_high_risk_over_selection() -> None:
    ref = _selection_ref(
        authority=DomainConflictAuthority.UNCLASSIFIED,
        domain=PROJECT,
    )
    case = DomainConflictCase(
        id="selection-default-forced-high-risk",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.HIGH_RISK_DOMAIN_PRECEDENCE,
        ),
        highest_risk_domain=PROJECT,
    )

    _assert_selection_preserved(result)
