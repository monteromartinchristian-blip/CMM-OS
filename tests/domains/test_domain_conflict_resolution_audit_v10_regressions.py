"""Phase 10.32 independent audit V10 regression tests.

Finding discovered against phase-10.32-audit-v10.tar.gz at:
f0680dcefe47c9d26dc6e6354b3281fbb1ceb785

These tests must be observed RED before any V10 remediation production change.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ContradictionStatus
from cmm.cognitive.knowledge import Contradiction
from cmm.domains.conflict_adapters import adapt_knowledge_contradiction
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
)
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId

PROJECT = DomainId(slug="project")
FIXED_TIME = datetime(2026, 8, 28, tzinfo=timezone.utc)


def _knowledge_ref(
    status: ContradictionStatus,
) -> tuple[DomainConflictReference, tuple[DomainId, ...]]:
    contradiction = Contradiction(
        item_a_id="knowledge-a",
        item_b_id="knowledge-b",
        id=f"knowledge-v10-{status.value}",
        status=status,
        created_at=FIXED_TIME,
    )
    return adapt_knowledge_contradiction(
        contradiction,
        domain_ids=(PROJECT,),
    )


# ---------------------------------------------------------------------------
# M22 — only an explicitly RESOLVED Phase 8 contradiction may enter a
#        RESOLVED Phase 10.32 case.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    (
        ContradictionStatus.DEFERRED,
        ContradictionStatus.ACKNOWLEDGED,
    ),
)
def test_audit_v10_m22_nonresolved_cognitive_status_cannot_enter_resolved_case(
    status: ContradictionStatus,
) -> None:
    ref, domains = _knowledge_ref(status)

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id=f"resolved-{status.value}-knowledge",
            domains=domains,
            kind=DomainConflictKind.KNOWLEDGE,
            severity=ref.severity,
            status=DomainConflictStatus.RESOLVED,
            references=(ref,),
            blocking=ref.blocking,
        )


def test_audit_v10_m22_knowledge_source_without_explicit_status_cannot_claim_resolved() -> (
    None
):
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.KNOWLEDGE_CONTRADICTION,
        source_id="knowledge-v10-missing-status",
        domain_id=PROJECT,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        metadata={},
    )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="resolved-knowledge-missing-status",
            domains=(PROJECT,),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.RESOLVED,
            references=(ref,),
            blocking=False,
        )


def test_audit_v10_m22_serialized_deferred_knowledge_resolved_case_is_typed_error() -> (
    None
):
    ref, domains = _knowledge_ref(ContradictionStatus.DEFERRED)
    case = DomainConflictCase(
        id="serialized-deferred-knowledge",
        domains=domains,
        kind=DomainConflictKind.KNOWLEDGE,
        severity=ref.severity,
        status=DomainConflictStatus.OPEN,
        references=(ref,),
        blocking=ref.blocking,
    )
    payload = case.to_dict()
    payload["status"] = "resolved"

    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(payload)


def test_audit_v10_m22_unknown_knowledge_status_cannot_claim_resolved() -> None:
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.KNOWLEDGE_CONTRADICTION,
        source_id="knowledge-v10-unknown-status",
        domain_id=PROJECT,
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        metadata={"status": "future_or_unknown"},
    )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="resolved-knowledge-unknown-status",
            domains=(PROJECT,),
            kind=DomainConflictKind.KNOWLEDGE,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.RESOLVED,
            references=(ref,),
            blocking=False,
        )


def test_audit_v10_m22_explicit_resolved_cognitive_status_remains_allowed() -> None:
    ref, domains = _knowledge_ref(ContradictionStatus.RESOLVED)

    case = DomainConflictCase(
        id="resolved-knowledge-positive-control",
        domains=domains,
        kind=DomainConflictKind.KNOWLEDGE,
        severity=ref.severity,
        status=DomainConflictStatus.RESOLVED,
        references=(ref,),
        blocking=ref.blocking,
    )

    assert case.status is DomainConflictStatus.RESOLVED
