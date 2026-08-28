"""Phase 10.32 independent audit V5 regression tests.

These tests encode findings discovered by the independent V5 audit of
phase-10.32-audit-v5.tar.gz at HEAD
8f255d4b1a7490398be148359bb07cdc52a7ce2e.

They must be observed RED before any V5 remediation production change.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.knowledge import Contradiction
from cmm.domains.conflict_adapters import (
    adapt_knowledge_contradiction,
    adapt_selection_conflict,
)
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
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.errors import DomainConflictResolutionContractError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult

RESOLVER = DomainConflictResolver()
PROJECT = DomainId(slug="project")
GENERAL = DomainId(slug="general")


def _ref(
    source_id: str,
    *,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
    domain: DomainId = PROJECT,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=domain,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=authority,
    )


def _knowledge_ref() -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    contradiction = Contradiction(
        item_a_id="knowledge-a",
        item_b_id="knowledge-b",
        id="knowledge-unresolved-v5",
        created_at=datetime.now(timezone.utc),
    )
    return adapt_knowledge_contradiction(
        contradiction,
        domain_ids=(PROJECT,),
    )


def _selection_ref() -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    ambiguity = DomainResolutionResult(
        id="selection-ambiguity-v5",
        context_id="ctx-selection-v5",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(PROJECT, GENERAL),
        requires_clarification=True,
        recommended_question="Which domain should take precedence?",
    )
    return adapt_selection_conflict(ambiguity)


# ---------------------------------------------------------------------------
# M11 — strategy/source eligibility must preserve Phase 8 and 10.31 ownership
# ---------------------------------------------------------------------------


def test_audit_v5_m11_unresolved_knowledge_cannot_resolve_via_most_restrictive() -> (
    None
):
    ref, domains = _knowledge_ref()
    assert ref.metadata["status"] == "unresolved"

    case = DomainConflictCase(
        id="knowledge-most-restrictive",
        domains=domains,
        kind=DomainConflictKind.KNOWLEDGE,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.winning_reference_ids == ()
    assert result.conflict_preserved is True
    assert result.can_proceed is False


def test_audit_v5_m11_selection_ambiguity_cannot_resolve_via_most_restrictive() -> None:
    ref, domains = _selection_ref()

    case = DomainConflictCase(
        id="selection-most-restrictive",
        domains=domains,
        kind=DomainConflictKind.SELECTION,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.winning_reference_ids == ()
    assert result.can_proceed is False


def test_audit_v5_m11_knowledge_source_kind_cannot_be_score_resolved_when_case_kind_is_other() -> (
    None
):
    ref, domains = _knowledge_ref()

    case = DomainConflictCase(
        id="knowledge-source-boundary",
        domains=domains,
        kind=DomainConflictKind.OTHER,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED
        ),
        evidence_scores={ref.source_id: 1.0},
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.winning_reference_ids == ()
    assert result.can_proceed is False


def test_audit_v5_m11_selection_source_kind_cannot_be_score_resolved_when_case_kind_is_other() -> (
    None
):
    ref, domains = _selection_ref()

    case = DomainConflictCase(
        id="selection-source-boundary",
        domains=domains,
        kind=DomainConflictKind.OTHER,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED
        ),
        evidence_scores={ref.source_id: 1.0},
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.winning_reference_ids == ()
    assert result.can_proceed is False


def test_audit_v5_m11_unclassified_preference_cannot_resolve_via_most_restrictive() -> (
    None
):
    ref = _ref("preference-unclassified")
    case = DomainConflictCase(
        id="preference-most-restrictive",
        domains=(PROJECT,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.winning_reference_ids == ()
    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M12 — caller-supplied case status may not contradict upstream state
# ---------------------------------------------------------------------------


def test_audit_v5_m12_unresolved_knowledge_reference_cannot_enter_resolved_case() -> (
    None
):
    ref, domains = _knowledge_ref()

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="resolved-unresolved-knowledge",
            domains=domains,
            kind=DomainConflictKind.KNOWLEDGE,
            severity=ref.severity,
            status=DomainConflictStatus.RESOLVED,
            references=(ref,),
            blocking=False,
        )


def test_audit_v5_m12_selection_requiring_clarification_cannot_enter_resolved_case() -> (
    None
):
    ref, domains = _selection_ref()
    assert ref.metadata["requires_clarification"] is True

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="resolved-selection-ambiguity",
            domains=domains,
            kind=DomainConflictKind.SELECTION,
            severity=ref.severity,
            status=DomainConflictStatus.RESOLVED,
            references=(ref,),
            blocking=False,
        )


# ---------------------------------------------------------------------------
# M13 — resolution semantic sets must agree with unresolved/declarative states
# ---------------------------------------------------------------------------


def test_audit_v5_m13_unresolved_resolution_cannot_claim_winner() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="unresolved-winner",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            winning_reference_ids=("winner",),
            preserved_reference_ids=("other",),
            reason_codes=(DomainConflictReasonCode.SEPARATE_RESULTS,),
            conflict_preserved=True,
            can_proceed=False,
        )


@pytest.mark.parametrize(
    ("winning", "rejected"),
    (
        (("winner",), ()),
        ((), ("rejected",)),
    ),
)
def test_audit_v5_m13_maintain_conflict_cannot_select_or_reject(
    winning: tuple[str, ...],
    rejected: tuple[str, ...],
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="maintain-semantic-choice",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            winning_reference_ids=winning,
            preserved_reference_ids=("preserved",),
            rejected_reference_ids=rejected,
            reason_codes=(DomainConflictReasonCode.PRESERVED,),
            conflict_preserved=True,
            can_proceed=False,
        )


@pytest.mark.parametrize(
    ("winning", "rejected"),
    (
        (("winner",), ()),
        ((), ("rejected",)),
    ),
)
def test_audit_v5_m13_separate_results_cannot_select_or_reject(
    winning: tuple[str, ...],
    rejected: tuple[str, ...],
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="separate-semantic-choice",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            winning_reference_ids=winning,
            preserved_reference_ids=("preserved",),
            rejected_reference_ids=rejected,
            reason_codes=(DomainConflictReasonCode.SEPARATE_RESULTS,),
            conflict_preserved=True,
            can_proceed=True,
        )


@pytest.mark.parametrize(
    ("status", "strategy", "flag_name", "reason"),
    (
        (
            DomainConflictStatus.AWAITING_USER,
            DomainConflictStrategy.ASK_USER,
            "requires_user_input",
            DomainConflictReasonCode.USER_INPUT_REQUIRED,
        ),
        (
            DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            DomainConflictStrategy.HUMAN_REVIEW,
            "requires_human_review",
            DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,
        ),
        (
            DomainConflictStatus.POSTPONED,
            DomainConflictStrategy.POSTPONE_ACTION,
            "action_postponed",
            DomainConflictReasonCode.ACTION_POSTPONED,
        ),
    ),
)
def test_audit_v5_m13_declarative_pending_state_cannot_already_claim_winner(
    status: DomainConflictStatus,
    strategy: DomainConflictStrategy,
    flag_name: str,
    reason: DomainConflictReasonCode,
) -> None:
    kwargs = {flag_name: True}
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="pending-winner",
            status=status,
            strategy=strategy,
            winning_reference_ids=("winner",),
            preserved_reference_ids=("preserved",),
            reason_codes=(reason,),
            conflict_preserved=True,
            can_proceed=False,
            **kwargs,
        )


def test_audit_v5_m13_preserved_ids_require_conflict_preserved_flag() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="preserved-flag-false",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            winning_reference_ids=("winner",),
            preserved_reference_ids=("preserved",),
            reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
            conflict_preserved=False,
            can_proceed=True,
        )


def test_audit_v5_m13_preserved_and_rejected_ids_must_be_disjoint() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="preserved-rejected-overlap",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            preserved_reference_ids=("same",),
            rejected_reference_ids=("same",),
            reason_codes=(DomainConflictReasonCode.SEPARATE_RESULTS,),
            conflict_preserved=True,
            can_proceed=False,
        )


# ---------------------------------------------------------------------------
# m7 — every non-trivial resolution must be auditable by reason code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    (
        {
            "status": DomainConflictStatus.RESOLVED,
            "strategy": DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            "winning_reference_ids": ("winner",),
            "conflict_preserved": False,
            "can_proceed": True,
        },
        {
            "status": DomainConflictStatus.UNRESOLVED,
            "strategy": DomainConflictStrategy.MAINTAIN_CONFLICT,
            "preserved_reference_ids": ("preserved",),
            "conflict_preserved": True,
            "can_proceed": False,
        },
    ),
)
def test_audit_v5_minor7_nontrivial_resolution_requires_reason_code(
    payload: dict[str, object],
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="missing-reason-code",
            **payload,
        )


# ---------------------------------------------------------------------------
# V5 remediation hardening — added RED before production remediation
# ---------------------------------------------------------------------------


def test_audit_v5_m11_knowledge_source_boundary_blocks_most_restrictive_when_kind_other() -> (
    None
):
    ref, domains = _knowledge_ref()
    case = DomainConflictCase(
        id="knowledge-source-most-restrictive",
        domains=domains,
        kind=DomainConflictKind.OTHER,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )
    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
    )
    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False


def test_audit_v5_m11_selection_source_boundary_blocks_most_restrictive_when_kind_other() -> (
    None
):
    ref, domains = _selection_ref()
    case = DomainConflictCase(
        id="selection-source-most-restrictive",
        domains=domains,
        kind=DomainConflictKind.OTHER,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=False,
    )
    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.MOST_RESTRICTIVE
        ),
    )
    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False


def test_audit_v5_m11_knowledge_source_boundary_blocks_high_risk_when_kind_other() -> (
    None
):
    from dataclasses import replace

    ref, domains = _knowledge_ref()
    risk_ref = replace(
        ref,
        domain_id=PROJECT,
        authority_kind=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="knowledge-source-high-risk",
        domains=domains,
        kind=DomainConflictKind.OTHER,
        severity=risk_ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(risk_ref,),
        blocking=risk_ref.blocking,
    )
    result = RESOLVER.resolve(case, highest_risk_domain=PROJECT)
    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False


def test_audit_v5_m11_selection_source_boundary_blocks_primary_precedence() -> None:
    from dataclasses import replace

    ref, domains = _selection_ref()
    primary_ref = replace(
        ref,
        domain_id=PROJECT,
        authority_kind=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="selection-source-primary",
        domains=domains,
        kind=DomainConflictKind.SELECTION,
        severity=primary_ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(primary_ref,),
        blocking=False,
    )
    result = RESOLVER.resolve(case, primary_domain=PROJECT)
    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False


def test_audit_v5_m13_resolved_resolution_requires_a_winner() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="resolved-no-winner",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
            can_proceed=True,
        )


@pytest.mark.parametrize(
    ("status", "strategy", "flag_name", "reason"),
    (
        (
            DomainConflictStatus.AWAITING_USER,
            DomainConflictStrategy.ASK_USER,
            "requires_user_input",
            DomainConflictReasonCode.USER_INPUT_REQUIRED,
        ),
        (
            DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            DomainConflictStrategy.HUMAN_REVIEW,
            "requires_human_review",
            DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,
        ),
    ),
)
def test_audit_v5_m13_input_or_review_pending_cannot_proceed(
    status: DomainConflictStatus,
    strategy: DomainConflictStrategy,
    flag_name: str,
    reason: DomainConflictReasonCode,
) -> None:
    kwargs = {flag_name: True}
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="pending-can-proceed",
            status=status,
            strategy=strategy,
            preserved_reference_ids=("preserved",),
            reason_codes=(reason,),
            conflict_preserved=True,
            can_proceed=True,
            **kwargs,
        )


@pytest.mark.parametrize(
    ("status", "strategy", "flag_name", "reason"),
    (
        (
            DomainConflictStatus.AWAITING_USER,
            DomainConflictStrategy.ASK_USER,
            "requires_user_input",
            DomainConflictReasonCode.USER_INPUT_REQUIRED,
        ),
        (
            DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            DomainConflictStrategy.HUMAN_REVIEW,
            "requires_human_review",
            DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,
        ),
        (
            DomainConflictStatus.POSTPONED,
            DomainConflictStrategy.POSTPONE_ACTION,
            "action_postponed",
            DomainConflictReasonCode.ACTION_POSTPONED,
        ),
    ),
)
def test_audit_v5_m13_pending_state_cannot_reject_reference(
    status: DomainConflictStatus,
    strategy: DomainConflictStrategy,
    flag_name: str,
    reason: DomainConflictReasonCode,
) -> None:
    kwargs = {flag_name: True}
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="pending-rejected",
            status=status,
            strategy=strategy,
            preserved_reference_ids=("preserved",),
            rejected_reference_ids=("rejected",),
            reason_codes=(reason,),
            conflict_preserved=True,
            can_proceed=False,
            **kwargs,
        )


def test_audit_v5_m13_winning_and_preserved_ids_must_be_disjoint() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="winner-preserved-overlap",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            winning_reference_ids=("same",),
            preserved_reference_ids=("same",),
            reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
            conflict_preserved=False,
            can_proceed=True,
        )
