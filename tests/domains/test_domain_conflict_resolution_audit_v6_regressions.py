"""Phase 10.32 independent audit V6 regression tests.

These tests encode findings discovered by the independent V6 audit of
phase-10.32-audit-v6.tar.gz at HEAD
f9bbdb7848260f08813d32ec412928cadf4b32da.

They must be observed RED before any V6 remediation production change.
"""

from __future__ import annotations

import pytest

from cmm.domains.composition_contracts import DomainCompositionConflict
from cmm.domains.conflict_adapters import (
    adapt_composition_conflict,
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
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult

RESOLVER = DomainConflictResolver()
PROJECT = DomainId(slug="project")
GENERAL = DomainId(slug="general")


def _ref(
    source_id: str,
    authority: DomainConflictAuthority,
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
# B5 — blocking/severity consistency is authoritative at Reference level
# ---------------------------------------------------------------------------


def test_audit_v6_b5_blocking_severity_requires_blocking_true() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
            source_id="blocking-severity",
            blocking=False,
            severity=DomainConflictSeverity.BLOCKING,
        )


def test_audit_v6_b5_blocking_true_rejects_nonblocking_severity() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
            source_id="blocking-flag",
            blocking=True,
            severity=DomainConflictSeverity.MATERIAL,
        )


def test_audit_v6_b5_serialized_blocking_mismatch_uses_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_kind": "domain_specific_conflict",
                "source_id": "serialized-blocking-mismatch",
                "blocking": False,
                "severity": "blocking",
            }
        )


# ---------------------------------------------------------------------------
# B6 — PermissionConflict source semantics cannot be downgraded by callers
# ---------------------------------------------------------------------------


def test_audit_v6_b6_permission_source_is_always_blocking() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
            source_id="permission-nonblocking",
            blocking=False,
            severity=DomainConflictSeverity.MATERIAL,
            authority_kind=DomainConflictAuthority.EVIDENCE,
        )


@pytest.mark.parametrize(
    "authority",
    (
        DomainConflictAuthority.EVIDENCE,
        DomainConflictAuthority.USER,
        DomainConflictAuthority.PRIMARY_DOMAIN,
    ),
)
def test_audit_v6_b6_permission_source_cannot_claim_lower_authority(
    authority: DomainConflictAuthority,
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
            source_id=f"permission-{authority.value}",
            blocking=True,
            severity=DomainConflictSeverity.BLOCKING,
            authority_kind=authority,
        )


def test_audit_v6_b6_serialized_permission_authority_downgrade_is_typed() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_kind": "permission_conflict",
                "source_id": "permission-evidence",
                "blocking": True,
                "severity": "blocking",
                "authority_kind": "evidence",
            }
        )


# ---------------------------------------------------------------------------
# M14 — requires_human_review is a procedural gate below hard/risk authority
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("authority", "kind", "kwargs"),
    (
        (
            DomainConflictAuthority.PRIMARY_DOMAIN,
            DomainConflictKind.DOMAIN_PRECEDENCE,
            {"primary_domain": PROJECT},
        ),
        (
            DomainConflictAuthority.EVIDENCE,
            DomainConflictKind.EVIDENCE,
            {"evidence_scores": {"ref": 1.0}},
        ),
        (
            DomainConflictAuthority.RELIABILITY,
            DomainConflictKind.RELIABILITY,
            {"reliability_scores": {"ref": 1.0}},
        ),
        (
            DomainConflictAuthority.TEMPORAL,
            DomainConflictKind.TEMPORAL,
            {"temporal_scores": {"ref": 1.0}},
        ),
    ),
)
def test_audit_v6_m14_required_human_review_blocks_primary_and_epistemic_resolution(
    authority: DomainConflictAuthority,
    kind: DomainConflictKind,
    kwargs: dict[str, object],
) -> None:
    ref = _ref("ref", authority)
    case = DomainConflictCase(
        id=f"human-{authority.value}",
        domains=(PROJECT,),
        kind=kind,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        requires_human_review=True,
    )

    result = RESOLVER.resolve(case, **kwargs)

    assert result.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
    assert result.strategy is DomainConflictStrategy.HUMAN_REVIEW
    assert result.requires_human_review is True
    assert result.requires_user_input is False
    assert result.can_proceed is False


def test_audit_v6_m14_required_human_review_disabled_fails_closed() -> None:
    ref = _ref("ref", DomainConflictAuthority.EVIDENCE)
    case = DomainConflictCase(
        id="human-disabled-evidence",
        domains=(PROJECT,),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        requires_human_review=True,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(allow_human_review=False),
        evidence_scores={"ref": 1.0},
    )

    assert result.status in {
        DomainConflictStatus.UNRESOLVED,
        DomainConflictStatus.BLOCKED,
    }
    assert result.conflict_preserved is True
    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M15 — Phase 10.31 ambiguity requiring clarification cannot continue
# ---------------------------------------------------------------------------


def test_audit_v6_m15_selection_clarification_separate_results_cannot_proceed() -> None:
    upstream = DomainResolutionResult(
        id="selection-v6",
        context_id="ctx-v6",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(PROJECT, GENERAL),
        requires_clarification=True,
        recommended_question="Which domain should take precedence?",
    )
    ref, domains = adapt_selection_conflict(upstream)

    case = DomainConflictCase(
        id="selection-case-v6",
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
            default_strategy=DomainConflictStrategy.SEPARATE_RESULTS,
            allow_separate_results=True,
        ),
    )

    assert result.status is DomainConflictStatus.UNRESOLVED
    assert result.conflict_preserved is True
    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M16 — remaining status semantics must reject impossible contract states
# ---------------------------------------------------------------------------


def test_audit_v6_m16_resolution_output_cannot_remain_open() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="open-output",
            status=DomainConflictStatus.OPEN,
            strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
            reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
            can_proceed=False,
        )


def test_audit_v6_m16_awaiting_user_case_cannot_delegate_knowledge_truth() -> None:
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.KNOWLEDGE_CONTRADICTION,
        source_id="knowledge-v6",
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        metadata={"status": "unresolved"},
    )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="knowledge-awaiting-user",
            domains=(),
            kind=DomainConflictKind.KNOWLEDGE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_USER,
            references=(ref,),
            blocking=False,
        )


# ---------------------------------------------------------------------------
# m8 — adapters copy categorical state, not arbitrary resolution narratives
# ---------------------------------------------------------------------------


def test_audit_v6_minor8_composition_adapter_omits_free_form_resolution_text() -> None:
    source = DomainCompositionConflict(
        code="COMP",
        category="policy",
        domains=(PROJECT, GENERAL),
        severity="material",
        message="message must not be copied",
        blocking=False,
        resolved=True,
        resolution="private free-form resolution narrative",
    )

    ref, _ = adapt_composition_conflict(source, source_id="composition-v6")

    assert "resolution" not in ref.metadata
    assert "private free-form resolution narrative" not in str(ref.metadata)
    assert ref.metadata["resolved_upstream"] is True
