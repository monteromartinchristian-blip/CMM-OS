"""Phase 10.32 — Domain Conflict Resolution tests."""

from __future__ import annotations

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.identifiers import DomainId


def _ref(
    source_id: str = "ref-1",
    *,
    domain_slug: str | None = None,
    blocking: bool = False,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug=domain_slug) if domain_slug else None,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


def test_permission_beats_primary_even_when_primary_has_stronger_evidence() -> None:
    resolver = DomainConflictResolver()
    ref_perm = _ref(
        "perm-1",
        domain_slug="general",
        blocking=True,
        authority=DomainConflictAuthority.PERMISSION,
    )
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-perm-prim",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.PERMISSION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_perm, ref_primary),
        blocking=True,
    )

    resolution = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),
        evidence_scores={"perm-1": 0.2, "prim-1": 0.99},
    )

    assert (
        resolution.status is DomainConflictStatus.RESOLVED
        or resolution.status is DomainConflictStatus.BLOCKED
    )
    # Permission deny restriction governs or case is blocked; never allows primary to win
    assert "prim-1" not in resolution.winning_reference_ids
    assert resolution.can_proceed is False


def test_mandatory_rule_beats_high_risk_and_primary() -> None:
    resolver = DomainConflictResolver()
    ref_mandatory = _ref(
        "mand-1",
        domain_slug="compliance",
        blocking=True,
        authority=DomainConflictAuthority.MANDATORY_RULE,
    )
    ref_risk = _ref(
        "risk-1",
        domain_slug="finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-mand-risk",
        domains=(DomainId(slug="compliance"), DomainId(slug="finance")),
        kind=DomainConflictKind.MANDATORY_RULE,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_mandatory, ref_risk),
        blocking=True,
    )

    resolution = resolver.resolve(
        case,
        highest_risk_domain=DomainId(slug="finance"),
    )
    assert "risk-1" not in resolution.winning_reference_ids
    assert resolution.can_proceed is False


def test_high_risk_beats_primary_when_structured_risk_domain_is_supplied() -> None:
    resolver = DomainConflictResolver()
    ref_risk = _ref(
        "risk-1",
        domain_slug="finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-risk-prim",
        domains=(DomainId(slug="finance"), DomainId(slug="project")),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_risk, ref_primary),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),
        highest_risk_domain=DomainId(slug="finance"),
    )
    assert resolution.winning_reference_ids == ("risk-1",)
    assert resolution.rejected_reference_ids == ("prim-1",)
    assert DomainConflictReasonCode.HIGH_RISK_PRECEDENCE in resolution.reason_codes
    assert resolution.can_proceed is True


def test_primary_beats_evidence_only_when_primary_strategy_is_legitimate() -> None:
    resolver = DomainConflictResolver()
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref_evidence = _ref(
        "ev-1",
        domain_slug="general",
        blocking=False,
        authority=DomainConflictAuthority.EVIDENCE,
    )
    case = DomainConflictCase(
        id="case-prim-ev",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.DOMAIN_PRECEDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_primary, ref_evidence),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),
        evidence_scores={"prim-1": 0.4, "ev-1": 0.9},
    )
    assert resolution.winning_reference_ids == ("prim-1",)
    assert resolution.rejected_reference_ids == ("ev-1",)
    assert DomainConflictReasonCode.PRIMARY_PRECEDENCE in resolution.reason_codes
    assert resolution.can_proceed is True


def test_unresolved_blocking_conflict_never_can_proceed() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ref-1", blocking=True, authority=DomainConflictAuthority.UNCLASSIFIED)
    ref2 = _ref("ref-2", blocking=True, authority=DomainConflictAuthority.UNCLASSIFIED)
    case = DomainConflictCase(
        id="case-block-unres",
        domains=(DomainId(slug="project"),),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=True,
    )

    resolution = resolver.resolve(case)
    assert resolution.status is DomainConflictStatus.BLOCKED
    assert resolution.can_proceed is False
    assert resolution.conflict_preserved is True
    assert set(resolution.preserved_reference_ids) == {"ref-1", "ref-2"}
    assert DomainConflictReasonCode.BLOCKING_UNRESOLVED in resolution.reason_codes
