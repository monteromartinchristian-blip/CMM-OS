"""Phase 10.32 independent audit V2 regression tests.

These tests encode the independent V2 findings discovered on audit bundle
HEAD 42a68dc81a15571a3408ff67add967f43a6baee8.

They must be observed RED before any V2 remediation production change.
"""

from __future__ import annotations

import pytest

from cmm.domains.conflict_adapters import adapt_declared_domain_conflict
from cmm.domains.conflict_resolution import DomainConflictResolver
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.contracts import DomainConflict
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId


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
# B2 — high-risk authority must not be weakened by configurable lower strategies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unsafe_strategy",
    (
        DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
        DomainConflictStrategy.EVIDENCE_WEIGHTED,
        DomainConflictStrategy.SEPARATE_RESULTS,
        DomainConflictStrategy.ASK_USER,
    ),
)
def test_audit_v2_b2_policy_rejects_unsafe_high_risk_strategy(
    unsafe_strategy: DomainConflictStrategy,
) -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(high_risk_strategy=unsafe_strategy)


# ---------------------------------------------------------------------------
# M4 — required human review cannot be downgraded to ordinary user confirmation
# ---------------------------------------------------------------------------


def test_audit_v2_m4_case_level_human_review_requirement_is_authoritative() -> None:
    project = DomainId(slug="project")
    case = DomainConflictCase(
        id="human-required",
        domains=(project,),
        kind=DomainConflictKind.PREFERENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref(
                "user-a",
                authority=DomainConflictAuthority.USER,
                domain=project,
            ),
            _ref(
                "user-b",
                authority=DomainConflictAuthority.USER,
                domain=project,
            ),
        ),
        requires_human_review=True,
    )

    out = DomainConflictResolver().resolve(case)

    assert out.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
    assert out.strategy is DomainConflictStrategy.HUMAN_REVIEW
    assert out.requires_human_review is True
    assert out.requires_user_input is False
    assert out.can_proceed is False


def test_audit_v2_m4_human_review_beats_user_regardless_reference_order() -> None:
    project = DomainId(slug="project")

    results = []
    for references in (
        (
            _ref(
                "user",
                authority=DomainConflictAuthority.USER,
                domain=project,
            ),
            _ref(
                "human",
                authority=DomainConflictAuthority.HUMAN_REVIEW,
                domain=project,
            ),
        ),
        (
            _ref(
                "human",
                authority=DomainConflictAuthority.HUMAN_REVIEW,
                domain=project,
            ),
            _ref(
                "user",
                authority=DomainConflictAuthority.USER,
                domain=project,
            ),
        ),
    ):
        case = DomainConflictCase(
            id="mixed-user-human",
            domains=(project,),
            kind=DomainConflictKind.PREFERENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=references,
        )
        results.append(DomainConflictResolver().resolve(case))

    for out in results:
        assert out.status is DomainConflictStatus.AWAITING_HUMAN_REVIEW
        assert out.strategy is DomainConflictStrategy.HUMAN_REVIEW
        assert out.requires_human_review is True
        assert out.requires_user_input is False


# ---------------------------------------------------------------------------
# m3 — malformed serialized collection values must keep the typed error boundary
# ---------------------------------------------------------------------------


def test_audit_v2_minor3_reference_none_collection_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_kind": "domain_specific_conflict",
                "source_id": "ref-none",
                "evidence_refs": None,
            }
        )


def test_audit_v2_minor3_case_none_collection_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(
            {
                "id": "case-none",
                "domains": None,
                "kind": "other",
                "severity": "material",
                "status": "open",
                "references": [
                    {
                        "source_kind": "domain_specific_conflict",
                        "source_id": "ref-1",
                    }
                ],
            }
        )


def test_audit_v2_minor3_resolution_none_collection_is_typed_error() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolution.from_dict(
            {
                "conflict_id": "resolution-none",
                "status": "unresolved",
                "strategy": "maintain_conflict",
                "preserved_reference_ids": ["ref-1"],
                "reason_codes": None,
                "conflict_preserved": True,
                "can_proceed": False,
            }
        )


# ---------------------------------------------------------------------------
# m4 — adapters must not copy free-form declaration reason text
# ---------------------------------------------------------------------------


def test_audit_v2_minor4_declared_adapter_omits_free_form_reason() -> None:
    conflict = DomainConflict(
        domain_id=DomainId(slug="project"),
        reason="potentially sensitive free-form declaration text",
        severity="material",
    )

    ref, _ = adapt_declared_domain_conflict(
        conflict,
        source_id="declared-1",
    )

    assert "reason" not in ref.metadata
    assert ref.metadata["declared_severity"] == "material"
