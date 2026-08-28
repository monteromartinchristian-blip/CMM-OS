"""Phase 10.32 — Domain Conflict Resolution tests."""

from __future__ import annotations

import pytest

from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.errors import DomainConflictResolutionContractError
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


def test_high_risk_requires_explicit_structured_domain() -> None:
    resolver = DomainConflictResolver()
    ref_risk = _ref(
        "risk-1",
        domain_slug="finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    ref_other = _ref(
        "other-1",
        domain_slug="project",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-risk-unspec",
        domains=(DomainId(slug="finance"), DomainId(slug="project")),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_risk, ref_other),
        blocking=False,
    )

    resolution = resolver.resolve(case, highest_risk_domain=None)
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.conflict_preserved is True
    assert resolution.can_proceed is False


def test_high_risk_never_uses_slug_name_heuristics() -> None:
    resolver = DomainConflictResolver()
    ref_health = _ref(
        "health-1",
        domain_slug="health",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    ref_finance = _ref(
        "finance-1",
        domain_slug="finance",
        blocking=False,
        authority=DomainConflictAuthority.HIGH_RISK_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-slug-heur",
        domains=(DomainId(slug="health"), DomainId(slug="finance")),
        kind=DomainConflictKind.DOMAIN_RISK,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_health, ref_finance),
        blocking=False,
    )

    # Without explicit highest_risk_domain, neither auto-wins based on "health" or "finance" name
    resolution = resolver.resolve(case, highest_risk_domain=None)
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.conflict_preserved is True


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


def test_primary_precedence_requires_primary_participation() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref(
        "ref-1",
        domain_slug="general",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref2 = _ref(
        "ref-2",
        domain_slug="analytics",
        blocking=False,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-no-prim-part",
        domains=(DomainId(slug="general"), DomainId(slug="analytics")),
        kind=DomainConflictKind.DOMAIN_PRECEDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),  # project not in references
    )
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.conflict_preserved is True


def test_primary_precedence_never_resolves_blocking_case() -> None:
    resolver = DomainConflictResolver()
    ref_primary = _ref(
        "prim-1",
        domain_slug="project",
        blocking=True,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    ref_other = _ref(
        "other-1",
        domain_slug="general",
        blocking=True,
        authority=DomainConflictAuthority.PRIMARY_DOMAIN,
    )
    case = DomainConflictCase(
        id="case-prim-block",
        domains=(DomainId(slug="project"), DomainId(slug="general")),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.OPEN,
        references=(ref_primary, ref_other),
        blocking=True,
    )

    resolution = resolver.resolve(
        case,
        primary_domain=DomainId(slug="project"),
    )
    assert resolution.status is DomainConflictStatus.BLOCKED
    assert resolution.can_proceed is False
    assert resolution.conflict_preserved is True


def test_evidence_unique_maximum_wins() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-ev-unique",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        evidence_scores={"ev-1": 0.85, "ev-2": 0.60},
    )
    assert resolution.status is DomainConflictStatus.RESOLVED
    assert resolution.winning_reference_ids == ("ev-1",)
    assert resolution.rejected_reference_ids == ("ev-2",)
    assert DomainConflictReasonCode.EVIDENCE_PRECEDENCE in resolution.reason_codes
    assert resolution.can_proceed is True


def test_evidence_tie_preserves_conflict() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-ev-tie",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        evidence_scores={"ev-1": 0.80, "ev-2": 0.80},
    )
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.conflict_preserved is True
    assert resolution.can_proceed is False


def test_evidence_missing_score_preserves_conflict() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    ref2 = _ref("ev-2", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-ev-missing",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )

    resolution = resolver.resolve(
        case,
        evidence_scores={"ev-1": 0.90},  # missing score for ev-2
    )
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.conflict_preserved is True


def test_reliability_and_temporal_weighting() -> None:
    resolver = DomainConflictResolver()
    ref_rel1 = _ref("rel-1", authority=DomainConflictAuthority.RELIABILITY)
    ref_rel2 = _ref("rel-2", authority=DomainConflictAuthority.RELIABILITY)
    case_rel = DomainConflictCase(
        id="case-rel",
        domains=(),
        kind=DomainConflictKind.RELIABILITY,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_rel1, ref_rel2),
        blocking=False,
    )
    res_rel = resolver.resolve(
        case_rel, reliability_scores={"rel-1": 0.9, "rel-2": 0.3}
    )
    assert res_rel.winning_reference_ids == ("rel-1",)
    assert DomainConflictReasonCode.RELIABILITY_PRECEDENCE in res_rel.reason_codes

    ref_temp1 = _ref("temp-1", authority=DomainConflictAuthority.TEMPORAL)
    ref_temp2 = _ref("temp-2", authority=DomainConflictAuthority.TEMPORAL)
    case_temp = DomainConflictCase(
        id="case-temp",
        domains=(),
        kind=DomainConflictKind.TEMPORAL,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref_temp1, ref_temp2),
        blocking=False,
    )
    res_temp = resolver.resolve(
        case_temp, temporal_scores={"temp-1": 100.0, "temp-2": 200.0}
    )
    assert res_temp.winning_reference_ids == ("temp-2",)
    assert DomainConflictReasonCode.TEMPORAL_PRECEDENCE in res_temp.reason_codes


def test_separate_results_safe_non_blocking() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ref-1", authority=DomainConflictAuthority.UNCLASSIFIED)
    ref2 = _ref("ref-2", authority=DomainConflictAuthority.UNCLASSIFIED)
    case = DomainConflictCase(
        id="case-sep",
        domains=(),
        kind=DomainConflictKind.PRESENTATION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    policy = DomainConflictResolutionPolicy(
        default_strategy=DomainConflictStrategy.SEPARATE_RESULTS,
        allow_separate_results=True,
    )
    resolution = resolver.resolve(case, policy=policy)
    assert resolution.status is DomainConflictStatus.UNRESOLVED
    assert resolution.strategy is DomainConflictStrategy.SEPARATE_RESULTS
    assert resolution.conflict_preserved is True
    assert resolution.can_proceed is True
    assert DomainConflictReasonCode.SEPARATE_RESULTS in resolution.reason_codes


def test_ask_user_legitimate_authority() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("pref-1", authority=DomainConflictAuthority.USER)
    ref2 = _ref("pref-2", authority=DomainConflictAuthority.USER)
    case = DomainConflictCase(
        id="case-pref",
        domains=(),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    resolution = resolver.resolve(case)
    assert resolution.status is DomainConflictStatus.AWAITING_USER
    assert resolution.strategy is DomainConflictStrategy.ASK_USER
    assert resolution.requires_user_input is True
    assert resolution.can_proceed is False
    assert DomainConflictReasonCode.USER_INPUT_REQUIRED in resolution.reason_codes


def test_human_review_declarative() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("hr-1", authority=DomainConflictAuthority.HUMAN_REVIEW)
    ref2 = _ref("hr-2", authority=DomainConflictAuthority.HUMAN_REVIEW)
    case = DomainConflictCase(
        id="case-hr",
        domains=(),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1, ref2),
        blocking=False,
    )
    resolution = resolver.resolve(case)
    assert resolution.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
    assert resolution.strategy is DomainConflictStrategy.HUMAN_REVIEW
    assert resolution.requires_human_review is True
    assert resolution.can_proceed is False
    assert DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED in resolution.reason_codes


def test_postpone_action() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("post-1", authority=DomainConflictAuthority.UNCLASSIFIED)
    case = DomainConflictCase(
        id="case-post",
        domains=(),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    policy = DomainConflictResolutionPolicy(
        default_strategy=DomainConflictStrategy.POSTPONE_ACTION,
        allow_postpone=True,
    )
    resolution = resolver.resolve(case, policy=policy)
    assert resolution.status is DomainConflictStatus.POSTPONED
    assert resolution.strategy is DomainConflictStrategy.POSTPONE_ACTION
    assert resolution.action_postponed is True
    assert resolution.can_proceed is False
    assert DomainConflictReasonCode.ACTION_POSTPONED in resolution.reason_codes


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


def test_resolver_rejects_unknown_score_reference_id() -> None:
    resolver = DomainConflictResolver()
    ref1 = _ref("ev-1", authority=DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="case-bad-score",
        domains=(),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref1,),
        blocking=False,
    )
    with pytest.raises(DomainConflictResolutionContractError):
        resolver.resolve(case, evidence_scores={"unknown-ref": 0.5})
