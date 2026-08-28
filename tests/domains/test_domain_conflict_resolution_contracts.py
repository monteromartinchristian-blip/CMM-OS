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


# ── Task 2 Contract Tests ─────────────────────────────────────────────────────

from cmm.domains.conflict_resolution_contracts import (
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictResolution,
    DomainConflictResolutionPolicy,
    DomainConflictStatus,
    DomainConflictStrategy,
)


def _ref(
    source_id: str = "ref-1",
    *,
    blocking: bool = False,
    authority: DomainConflictAuthority | None = None,
) -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        blocking=blocking,
        severity=(
            DomainConflictSeverity.BLOCKING
            if blocking
            else DomainConflictSeverity.MATERIAL
        ),
        authority_kind=authority,
    )


def test_case_rejects_blocking_flag_without_blocking_severity() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.COMPOSITION,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(_ref(blocking=True),),
            blocking=True,
        )


def test_case_rejects_resolved_with_blocking_reference() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.PERMISSION,
            severity=DomainConflictSeverity.BLOCKING,
            status=DomainConflictStatus.RESOLVED,
            references=(_ref(blocking=True),),
            blocking=True,
        )


def test_case_is_frozen_deeply_and_round_trips() -> None:
    metadata = {"key": "val", "list": [1, 2]}
    case = DomainConflictCase(
        id="case-1",
        domains=(
            DomainId(slug="project"),
            DomainId(slug="project"),
            DomainId(slug="general"),
        ),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.BLOCKING,
        status=DomainConflictStatus.BLOCKED,
        references=(_ref("ref-1", blocking=True), _ref("ref-2", blocking=False)),
        affected_item_refs=("item-1",),
        candidate_strategies=(DomainConflictStrategy.MOST_RESTRICTIVE,),
        requires_human_review=False,
        blocking=True,
        metadata=metadata,
    )
    assert case.domains == (DomainId(slug="project"), DomainId(slug="general"))
    assert isinstance(case.metadata, MappingProxyType)
    metadata["list"].append(3)
    assert tuple(case.metadata["list"]) == (1, 2)
    assert DomainConflictCase.from_dict(case.to_dict()) == case


def test_case_rejects_duplicate_references() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.SAFETY,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(_ref("ref-1"), _ref("ref-1")),
            blocking=False,
        )


def test_case_rejects_empty_references() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="case-1",
            domains=(DomainId(slug="project"),),
            kind=DomainConflictKind.SAFETY,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(),
            blocking=False,
        )


def test_resolution_rejects_blocking_unresolved_can_proceed() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-1",
            status=DomainConflictStatus.BLOCKED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            preserved_reference_ids=("ref-1",),
            reason_codes=(DomainConflictReasonCode.BLOCKING_UNRESOLVED,),
            conflict_preserved=True,
            can_proceed=True,
        )


def test_resolution_rejects_overlapping_winner_and_rejected() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="case-1",
            status=DomainConflictStatus.RESOLVED,
            strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
            winning_reference_ids=("ref-1",),
            rejected_reference_ids=("ref-1",),
            can_proceed=True,
        )


def test_resolution_from_dict_rejects_contradictory_user_state() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolution.from_dict(
            {
                "conflict_id": "case-1",
                "status": "resolved",
                "strategy": "ask_user",
                "winning_reference_ids": [],
                "preserved_reference_ids": [],
                "rejected_reference_ids": [],
                "reason_codes": ["DOMAIN_CONFLICT_USER_INPUT_REQUIRED"],
                "requires_user_input": True,
                "requires_human_review": False,
                "action_postponed": False,
                "conflict_preserved": False,
                "can_proceed": True,
                "metadata": {},
            }
        )


def test_resolution_is_frozen_deeply_and_round_trips() -> None:
    metadata = {"info": "test"}
    resolution = DomainConflictResolution(
        conflict_id="case-1",
        status=DomainConflictStatus.RESOLVED,
        strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
        winning_reference_ids=("ref-1",),
        rejected_reference_ids=("ref-2",),
        reason_codes=(DomainConflictReasonCode.PERMISSION_PRECEDENCE,),
        can_proceed=True,
        metadata=metadata,
    )
    assert isinstance(resolution.metadata, MappingProxyType)
    metadata["info"] = "mutated"
    assert resolution.metadata["info"] == "test"
    assert DomainConflictResolution.from_dict(resolution.to_dict()) == resolution


def test_policy_rejects_primary_precedence_for_permission_conflicts() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            permission_strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE
        )


def test_policy_rejects_disabled_human_review_strategy() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            default_strategy=DomainConflictStrategy.HUMAN_REVIEW,
            allow_human_review=False,
        )


def test_policy_rejects_disabled_preservation() -> None:
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(
            preserve_unresolved_conflicts=False,
        )


def test_policy_is_frozen_deeply_and_round_trips() -> None:
    metadata = {"setting": 123}
    policy = DomainConflictResolutionPolicy(metadata=metadata)
    assert isinstance(policy.metadata, MappingProxyType)
    metadata["setting"] = 456
    assert policy.metadata["setting"] == 123
    assert DomainConflictResolutionPolicy.from_dict(policy.to_dict()) == policy


def test_case_rejects_unknown_serialized_fields() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictCase.from_dict(
            {
                "id": "case-1",
                "domains": ["domain:project"],
                "kind": "composition",
                "severity": "material",
                "status": "open",
                "references": [
                    {
                        "source_kind": "composition_conflict",
                        "source_id": "c1",
                        "blocking": False,
                    }
                ],
                "extra": "bad",
            }
        )


def test_resolution_rejects_unknown_serialized_fields() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolution.from_dict(
            {
                "conflict_id": "case-1",
                "status": "unresolved",
                "strategy": "maintain_conflict",
                "conflict_preserved": True,
                "extra": "bad",
            }
        )


def test_policy_rejects_unknown_serialized_fields() -> None:
    with pytest.raises(DomainConflictResolutionSerializationError):
        DomainConflictResolutionPolicy.from_dict(
            {
                "extra": "bad",
            }
        )


def test_contracts_reject_credential_keys_in_metadata() -> None:
    bad_meta = {"api_key": "supersecret"}
    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictReference(
            source_kind=DomainConflictSourceKind.PERMISSION_CONFLICT,
            source_id="ref-1",
            metadata=bad_meta,
        )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictCase(
            id="c1",
            domains=(),
            kind=DomainConflictKind.OTHER,
            severity=DomainConflictSeverity.MATERIAL,
            status=DomainConflictStatus.OPEN,
            references=(_ref(),),
            metadata=bad_meta,
        )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolution(
            conflict_id="c1",
            status=DomainConflictStatus.UNRESOLVED,
            strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
            conflict_preserved=True,
            metadata=bad_meta,
        )

    with pytest.raises(DomainConflictResolutionContractError):
        DomainConflictResolutionPolicy(metadata=bad_meta)
