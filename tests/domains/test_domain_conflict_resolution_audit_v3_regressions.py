"""Phase 10.32 independent audit V3 regression tests.

These tests encode findings discovered by the independent V3 audit of
phase-10.32-audit-v3.tar.gz at HEAD
8940cabf9470862ba3d79207d78e90a7df801b61.

They must be observed RED before any V3 remediation production change.
"""

from __future__ import annotations

import pytest

from cmm.domains.composition_contracts import DomainCompositionPolicy
from cmm.domains.conflict_adapters import adapt_declared_domain_conflict
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
from cmm.domains.contracts import DomainConflict
from cmm.domains.errors import DomainConflictResolutionContractError
from cmm.domains.identifiers import DomainId

RESOLVER = DomainConflictResolver()
PROJECT = DomainId(slug="project")
GENERAL = DomainId(slug="general")


def _ref(
    source_id: str,
    *,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
    domain: DomainId = PROJECT,
    blocking: bool = False,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=domain,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


# ---------------------------------------------------------------------------
# B3 — declared high/critical conflicts must preserve blocking semantics
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("severity", ("critical", "high"))
def test_audit_v3_b3_declared_default_blocking_severity_is_preserved(
    severity: str,
) -> None:
    assert severity in DomainCompositionPolicy().blocking_severities

    ref, _ = adapt_declared_domain_conflict(
        DomainConflict(
            domain_id=PROJECT,
            reason="declared incompatibility",
            severity=severity,
        ),
        source_id=f"declared-{severity}",
    )

    assert ref.blocking is True
    assert ref.severity is DomainConflictSeverity.BLOCKING


def test_audit_v3_b3_declared_high_conflict_cannot_become_primary_can_proceed() -> None:
    ref, domains = adapt_declared_domain_conflict(
        DomainConflict(
            domain_id=PROJECT,
            reason="declared incompatibility",
            severity="high",
        ),
        source_id="declared-high",
        owner_domain_id=GENERAL,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )

    case = DomainConflictCase(
        id="declared-high-case",
        domains=domains,
        kind=DomainConflictKind.DOMAIN_PRECEDENCE,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    result = RESOLVER.resolve(case, primary_domain=PROJECT)

    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M6 — primary authority cannot be downgraded to evidence through policy
# ---------------------------------------------------------------------------


def test_audit_v3_m6_primary_policy_rejects_evidence_weighted_downgrade() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            primary_strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED
        )


# ---------------------------------------------------------------------------
# M7 — human/user escalation constraints must fail closed, not disappear/crash
# ---------------------------------------------------------------------------


def test_audit_v3_m7_required_human_review_unclassified_routes_to_human() -> None:
    case = DomainConflictCase(
        id="human-unclassified",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_ref("a"), _ref("b")),
        requires_human_review=True,
    )

    result = RESOLVER.resolve(case)

    assert result.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
    assert result.strategy is DomainConflictStrategy.HUMAN_REVIEW
    assert result.requires_human_review is True
    assert result.requires_user_input is False
    assert result.can_proceed is False


def test_audit_v3_m7_disabled_human_review_fails_closed_without_exception() -> None:
    case = DomainConflictCase(
        id="human-disabled",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("a", authority=DomainConflictAuthority.USER),
            _ref("b", authority=DomainConflictAuthority.USER),
        ),
        requires_human_review=True,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(allow_human_review=False),
    )

    assert result.can_proceed is False
    assert result.conflict_preserved is True
    assert result.status in {
        DomainConflictStatus.UNRESOLVED,
        DomainConflictStatus.BLOCKED,
    }


def test_audit_v3_m7_candidate_exclusion_of_human_fails_closed_without_exception() -> (
    None
):
    case = DomainConflictCase(
        id="human-candidate-excluded",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("a", authority=DomainConflictAuthority.USER),
            _ref("b", authority=DomainConflictAuthority.USER),
        ),
        requires_human_review=True,
        candidate_strategies=(DomainConflictStrategy.ASK_USER,),
    )

    result = RESOLVER.resolve(case)

    assert result.can_proceed is False
    assert result.conflict_preserved is True


def test_audit_v3_m7_resolved_case_cannot_still_require_human_review() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="resolved-human-required",
            domains=(PROJECT,),
            kind=DomainConflictKind.PREFERENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.RESOLVED,
            references=(_ref("a", authority=DomainConflictAuthority.USER),),
            requires_human_review=True,
        )


def test_audit_v3_m7_disabled_user_confirmation_fails_closed_without_exception() -> (
    None
):
    case = DomainConflictCase(
        id="user-disabled",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("a", authority=DomainConflictAuthority.USER),
            _ref("b", authority=DomainConflictAuthority.USER),
        ),
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(allow_user_confirmation=False),
    )

    assert result.can_proceed is False
    assert result.conflict_preserved is True


def test_audit_v3_m7_candidate_exclusion_of_user_fails_closed_without_exception() -> (
    None
):
    case = DomainConflictCase(
        id="user-candidate-excluded",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("a", authority=DomainConflictAuthority.USER),
            _ref("b", authority=DomainConflictAuthority.USER),
        ),
        candidate_strategies=(DomainConflictStrategy.MAINTAIN_CONFLICT,),
    )

    result = RESOLVER.resolve(case)

    assert result.can_proceed is False
    assert result.conflict_preserved is True


# ---------------------------------------------------------------------------
# M8 — resolution status/strategy/preservation states must be coherent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "strategy", "extra"),
    (
        (
            DomainConflictStatus.AWAITING_USER,
            DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            {"requires_user_input": True},
        ),
        (
            DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            {"requires_human_review": True},
        ),
        (
            DomainConflictStatus.POSTPONED,
            DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            {"action_postponed": True},
        ),
    ),
)
def test_audit_v3_m8_declarative_status_requires_matching_strategy(
    status: DomainConflictStatus,
    strategy: DomainConflictStrategy,
    extra: dict[str, bool],
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="status-strategy-mismatch",
            status=status,
            strategy=strategy,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.PRESERVED,),
            conflict_preserved=True,
            can_proceed=False,
            **extra,
        )


@pytest.mark.parametrize(
    "status",
    (DomainConflictStatus.UNRESOLVED, DomainConflictStatus.BLOCKED),
)
def test_audit_v3_m8_unresolved_or_blocked_requires_preserved_conflict(
    status: DomainConflictStatus,
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="not-preserved",
            status=status,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            reason_codes=(DomainConflictReasonCode.INSUFFICIENT_BASIS,),
            conflict_preserved=False,
            can_proceed=False,
        )


def test_audit_v3_m8_resolved_cannot_claim_conflict_is_still_preserved() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="resolved-preserved",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
            conflict_preserved=True,
            can_proceed=True,
        )


# ---------------------------------------------------------------------------
# m5 — reason codes must identify the actual authority, not global safety
# ---------------------------------------------------------------------------


def test_audit_v3_minor5_high_risk_most_restrictive_reason_is_high_risk() -> None:
    case = DomainConflictCase(
        id="risk-most-restrictive",
        domains=(PROJECT,),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref(
                "risk",
                authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
            ),
        ),
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            high_risk_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
        highest_risk_domain=PROJECT,
    )

    assert DomainConflictReasonCode.HIGH_RISK_PRECEDENCE in result.reason_codes
    assert DomainConflictReasonCode.SAFETY_PRECEDENCE not in result.reason_codes
