"""Phase 10.32 independent audit V8 regression tests.

Findings discovered against phase-10.32-audit-v8.tar.gz at:
006f13cd88f14746361837da8097e00fbd85a47a

These tests must be observed RED before any V8 remediation production change.
"""

from __future__ import annotations

import pytest

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
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId

PROJECT = DomainId(slug="project")
RESOLVER = DomainConflictResolver()


def _ref(
    authority: DomainConflictAuthority,
    *,
    source_id: str = "ref",
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=PROJECT,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=authority,
    )


# ---------------------------------------------------------------------------
# M19 — ASK_USER must respect effective authority, not only conflict kind
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind",
    (
        DomainConflictKind.RECOMMENDATION,
        DomainConflictKind.DOMAIN_PRECEDENCE,
    ),
)
def test_audit_v8_m19_evidence_authority_cannot_be_delegated_to_user(
    kind: DomainConflictKind,
) -> None:
    case = DomainConflictCase(
        id=f"evidence-ask-user-{kind.value}",
        domains=(PROJECT,),
        kind=kind,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_ref(DomainConflictAuthority.EVIDENCE),),
        candidate_strategies=(DomainConflictStrategy.ASK_USER,),
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            evidence_strategy=DomainConflictStrategy.ASK_USER,
        ),
    )

    assert result.status is not DomainConflictStatus.AWAITING_USER
    assert result.requires_user_input is False
    assert result.conflict_preserved is True
    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M20 — POSTPONED case state must be coherent with routable authority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "authority",
    (
        DomainConflictAuthority.GLOBAL_SAFETY,
        DomainConflictAuthority.RELIABILITY,
        DomainConflictAuthority.TEMPORAL,
        DomainConflictAuthority.USER,
        DomainConflictAuthority.HUMAN_REVIEW,
    ),
)
def test_audit_v8_m20_postponed_case_rejects_authority_that_cannot_route_postpone(
    authority: DomainConflictAuthority,
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id=f"postponed-{authority.value}",
            domains=(PROJECT,),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.POSTPONED,
            references=(_ref(authority),),
            candidate_strategies=(DomainConflictStrategy.POSTPONE_ACTION,),
        )


def test_audit_v8_m20_from_dict_rejects_impossible_postponed_global_safety_typed() -> (
    None
):
    payload = DomainConflictCase(
        id="postponed-global-safety-serialized",
        domains=(PROJECT,),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_ref(DomainConflictAuthority.GLOBAL_SAFETY),),
        candidate_strategies=(DomainConflictStrategy.POSTPONE_ACTION,),
    ).to_dict()
    payload["status"] = "postponed"

    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(payload)


@pytest.mark.parametrize(
    "authority",
    (
        DomainConflictAuthority.PRIMARY_DOMAIN,
        DomainConflictAuthority.EVIDENCE,
    ),
)
def test_audit_v8_m20_postponed_case_rejects_human_review_gate_below_hard_risk_authority(
    authority: DomainConflictAuthority,
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id=f"postponed-human-review-{authority.value}",
            domains=(PROJECT,),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.POSTPONED,
            references=(_ref(authority),),
            candidate_strategies=(DomainConflictStrategy.POSTPONE_ACTION,),
            requires_human_review=True,
        )
