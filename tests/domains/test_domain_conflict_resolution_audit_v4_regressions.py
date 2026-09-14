"""Phase 10.32 independent audit V4 regression tests.

These tests encode findings discovered by the independent V4 audit of
phase-10.32-audit-v4.tar.gz at HEAD
3b09ecea3af8a50214590f7afe2fe65f988a9acf.

They must be observed RED before any V4 remediation production change.
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
    authority: DomainConflictAuthority,
    domain: DomainId,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=domain,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=authority,
    )


# ---------------------------------------------------------------------------
# B4 — personal preference must never auto-resolve from scoring alone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("authority", "score_argument"),
    (
        (DomainConflictAuthority.EVIDENCE, "evidence_scores"),
        (DomainConflictAuthority.RELIABILITY, "reliability_scores"),
        (DomainConflictAuthority.TEMPORAL, "temporal_scores"),
    ),
)
def test_audit_v4_b4_preference_never_auto_resolves_from_scores(
    authority: DomainConflictAuthority,
    score_argument: str,
) -> None:
    case = DomainConflictCase(
        id=f"preference-{authority.value}",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref("a", authority=authority, domain=PROJECT),
            _ref("b", authority=authority, domain=GENERAL),
        ),
    )

    result = RESOLVER.resolve(
        case,
        **{score_argument: {"a": 0.90, "b": 0.10}},
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False
    assert result.conflict_preserved is True


# ---------------------------------------------------------------------------
# M9 — Phase 8 / Phase 10.31 boundaries cannot be resolved by scoring
# ---------------------------------------------------------------------------


def test_audit_v4_m9_selection_ambiguity_cannot_be_resolved_by_score() -> None:
    ambiguous = DomainResolutionResult(
        id="selection-ambiguity",
        context_id="ctx-selection",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(PROJECT, GENERAL),
        requires_clarification=True,
        recommended_question="Which domain should take precedence?",
    )

    ref, domains = adapt_selection_conflict(ambiguous)

    case = DomainConflictCase(
        id="selection-case",
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
            default_strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED
        ),
        evidence_scores={ref.source_id: 1.0},
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False
    assert result.conflict_preserved is True


def test_audit_v4_m9_unresolved_cognitive_reference_cannot_be_resolved_by_score() -> (
    None
):
    contradiction = Contradiction(
        item_a_id="knowledge-a",
        item_b_id="knowledge-b",
        id="cognitive-unresolved",
        created_at=datetime.now(timezone.utc),
    )

    ref, domains = adapt_knowledge_contradiction(
        contradiction,
        domain_ids=(PROJECT,),
    )

    assert ref.metadata["status"] == "unresolved"

    case = DomainConflictCase(
        id="knowledge-case",
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
            default_strategy=DomainConflictStrategy.EVIDENCE_WEIGHTED
        ),
        evidence_scores={ref.source_id: 1.0},
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False
    assert result.conflict_preserved is True


def test_audit_v4_m9_knowledge_kind_cannot_resolve_by_high_risk_precedence() -> None:
    case = DomainConflictCase(
        id="knowledge-risk",
        domains=(PROJECT, GENERAL),
        kind=DomainConflictKind.KNOWLEDGE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref(
                "project-knowledge",
                authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
                domain=PROJECT,
            ),
            _ref(
                "general-knowledge",
                authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
                domain=GENERAL,
            ),
        ),
    )

    result = RESOLVER.resolve(
        case,
        highest_risk_domain=PROJECT,
    )

    assert result.status is not DomainConflictStatus.RESOLVED
    assert result.can_proceed is False
    assert result.conflict_preserved is True


# ---------------------------------------------------------------------------
# M10 — preservation / postponement state must remain internally coherent
# ---------------------------------------------------------------------------


def test_audit_v4_m10_conflict_preserved_requires_preserved_reference_ids() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="missing-preserved-ids",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            reason_codes=(DomainConflictReasonCode.PRESERVED,),
            conflict_preserved=True,
            can_proceed=False,
        )


def test_audit_v4_m10_postponed_action_cannot_proceed() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="postponed-can-proceed",
            status=DomainConflictStatus.POSTPONED,
            strategy=DomainConflictStrategy.POSTPONE_ACTION,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.ACTION_POSTPONED,),
            action_postponed=True,
            conflict_preserved=True,
            can_proceed=True,
        )
