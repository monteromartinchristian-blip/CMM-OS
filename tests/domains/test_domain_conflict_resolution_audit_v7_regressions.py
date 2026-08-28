"""Phase 10.32 independent audit V7 regression tests.

Findings discovered against phase-10.32-audit-v7.tar.gz at:
8b8d672767d20feee29e19742cb4a9db02722475

These tests must be observed RED before any V7 remediation production change.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cmm.cognitive.knowledge import Contradiction
from cmm.domains.conflict_adapters import adapt_knowledge_contradiction
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
    source_id: str = "ref",
    *,
    authority: DomainConflictAuthority = DomainConflictAuthority.UNCLASSIFIED,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=PROJECT,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=authority,
    )


def _knowledge_ref() -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    contradiction = Contradiction(
        item_a_id="knowledge-a",
        item_b_id="knowledge-b",
        id="knowledge-v7",
        created_at=datetime.now(timezone.utc),
    )
    return adapt_knowledge_contradiction(
        contradiction,
        domain_ids=(PROJECT,),
    )


# ---------------------------------------------------------------------------
# M17 — ASK_USER must never cross Phase 8 knowledge-truth ownership
# ---------------------------------------------------------------------------


def test_audit_v7_m17_real_knowledge_source_cannot_be_delegated_by_default_ask_user() -> (
    None
):
    ref, domains = _knowledge_ref()
    case = DomainConflictCase(
        id="knowledge-user-default",
        domains=domains,
        kind=DomainConflictKind.RECOMMENDATION,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    result = RESOLVER.resolve(
        case,
        policy=DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.ASK_USER
        ),
    )

    assert result.status is not DomainConflictStatus.AWAITING_USER
    assert result.requires_user_input is False
    assert result.conflict_preserved is True
    assert result.can_proceed is False


def test_audit_v7_m17_real_knowledge_source_cannot_be_delegated_by_user_authority() -> (
    None
):
    ref, domains = _knowledge_ref()
    ref = replace(
        ref,
        authority_kind=DomainConflictAuthority.USER,
    )
    case = DomainConflictCase(
        id="knowledge-user-authority",
        domains=domains,
        kind=DomainConflictKind.RECOMMENDATION,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )

    result = RESOLVER.resolve(case)

    assert result.status is not DomainConflictStatus.AWAITING_USER
    assert result.requires_user_input is False
    assert result.conflict_preserved is True
    assert result.can_proceed is False


# ---------------------------------------------------------------------------
# M18 — declarative case statuses must be authority/strategy coherent
# ---------------------------------------------------------------------------


def test_audit_v7_m18_case_awaiting_user_rejects_factual_evidence_kind() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="evidence-await-user",
            domains=(PROJECT,),
            kind=DomainConflictKind.EVIDENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_USER,
            references=(
                _ref(
                    authority=DomainConflictAuthority.EVIDENCE,
                ),
            ),
        )


def test_audit_v7_m18_case_awaiting_user_rejects_global_safety_authority() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="safety-await-user",
            domains=(PROJECT,),
            kind=DomainConflictKind.PREFERENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_USER,
            references=(
                _ref(
                    authority=DomainConflictAuthority.GLOBAL_SAFETY,
                ),
            ),
        )


def test_audit_v7_m18_case_awaiting_human_rejects_global_safety_authority() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="safety-await-human",
            domains=(PROJECT,),
            kind=DomainConflictKind.SAFETY,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            references=(
                _ref(
                    authority=DomainConflictAuthority.GLOBAL_SAFETY,
                ),
            ),
            requires_human_review=True,
        )


def test_audit_v7_m18_awaiting_user_candidate_set_must_allow_ask_user() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="candidate-await-user",
            domains=(PROJECT,),
            kind=DomainConflictKind.PREFERENCE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_USER,
            references=(
                _ref(
                    authority=DomainConflictAuthority.USER,
                ),
            ),
            candidate_strategies=(DomainConflictStrategy.MAINTAIN_CONFLICT,),
        )


def test_audit_v7_m18_awaiting_human_candidate_set_must_allow_human_review() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="candidate-await-human",
            domains=(PROJECT,),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.AWAITING_HUMAN_REVIEW,
            references=(
                _ref(
                    authority=DomainConflictAuthority.HUMAN_REVIEW,
                ),
            ),
            candidate_strategies=(DomainConflictStrategy.MAINTAIN_CONFLICT,),
            requires_human_review=True,
        )


def test_audit_v7_m18_postponed_candidate_set_must_allow_postpone_action() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="candidate-postponed",
            domains=(PROJECT,),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.POSTPONED,
            references=(_ref(),),
            candidate_strategies=(DomainConflictStrategy.MAINTAIN_CONFLICT,),
        )


def test_audit_v7_m18_from_dict_rejects_illegitimate_awaiting_user_as_typed_error() -> (
    None
):
    payload = DomainConflictCase(
        id="serialized-evidence-open",
        domains=(PROJECT,),
        kind=DomainConflictKind.EVIDENCE,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(
            _ref(
                authority=DomainConflictAuthority.EVIDENCE,
            ),
        ),
    ).to_dict()
    payload["status"] = "awaiting_user"

    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(payload)


def test_audit_v7_m18_from_dict_rejects_candidate_postpone_mismatch_as_typed_error() -> (
    None
):
    payload = DomainConflictCase(
        id="serialized-postpone-open",
        domains=(PROJECT,),
        kind=DomainConflictKind.OTHER,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_ref(),),
        candidate_strategies=(DomainConflictStrategy.MAINTAIN_CONFLICT,),
    ).to_dict()
    payload["status"] = "postponed"

    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(payload)
