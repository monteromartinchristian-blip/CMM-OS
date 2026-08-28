"""Phase 10.32 — Domain Conflict Resolution Contracts tests."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictReference,
    DomainConflictSeverity,
    DomainConflictSourceKind,
)
from cmm.domains.errors import (
    DomainConflictResolutionContractError,
    DomainConflictResolutionSerializationError,
)
from cmm.domains.identifiers import DomainId


def test_reference_is_frozen_deeply_and_round_trips() -> None:
    metadata = {"classification": {"safe": True}, "labels": ["a", "b"]}
    ref = DomainConflictReference(
        source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
        source_id="permission-conflict-1",
        domain_id=DomainId(slug="project"),
        blocking=True,
        severity=DomainConflictSeverity.BLOCKING,
        authority_kind=DomainConflictAuthority.PERMISSION,
        evidence_refs=("evidence-1",),
        metadata=metadata,
    )

    metadata["classification"]["safe"] = False
    metadata["labels"].append("mutated")

    assert isinstance(ref.metadata, MappingProxyType)
    assert ref.metadata["classification"]["safe"] is True
    assert tuple(ref.metadata["labels"]) == ("a", "b")
    assert DomainConflictReference.from_dict(ref.to_dict()) == ref


def test_reference_rejects_non_strict_boolean() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
            source_id="permission-conflict-1",
            blocking=1,
        )


def test_reference_rejects_unknown_serialized_fields() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictReference.from_dict(
            {
                "source_kind": "permission_conflict",
                "source_id": "permission-conflict-1",
                "blocking": True,
                "unexpected": "no",
            }
        )


def test_reference_rejects_duplicate_evidence_refs() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
            source_id="evidence-conflict-1",
            blocking=False,
            evidence_refs=("e1", "e1"),
        )
