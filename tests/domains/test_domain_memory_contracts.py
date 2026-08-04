"""Tests for Phase 10.18 Domain Memory immutable contracts."""

import json
from types import MappingProxyType
from typing import Any

import pytest

from cmm.domains.errors import (
    DomainMemoryContractError,
    DomainMemoryPrivacyError,
    DomainMemorySerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.memory_contracts import (
    _DIGEST_PREFIX_LENGTH,
    DomainMemoryReference,
    DomainMemoryReferenceInventory,
    DomainMemoryReferenceKind,
    DomainMemorySelectionDecision,
    DomainMemorySelectionDecisionCode,
    DomainMemoryValidationCode,
    DomainMemoryValidationResult,
    DomainMemoryView,
    DomainMemoryViewRequest,
    DomainMemoryViewSnapshot,
    _sha256_digest,
)


def test_domain_memory_reference_kind_enum() -> None:
    assert DomainMemoryReferenceKind.KNOWLEDGE_ITEM.value == "knowledge_item"
    assert DomainMemoryReferenceKind.KNOWLEDGE_RELATION.value == "knowledge_relation"
    assert DomainMemoryReferenceKind.EVIDENCE.value == "evidence"
    assert DomainMemoryReferenceKind.RESOURCE.value == "resource"
    assert DomainMemoryReferenceKind.CONTRADICTION.value == "contradiction"
    assert DomainMemoryReferenceKind.VERSION.value == "version"
    assert (
        DomainMemoryReferenceKind.RESOLUTION_MEMORY_ENTRY.value
        == "resolution_memory_entry"
    )
    assert DomainMemoryReferenceKind.KNOWLEDGE_PACKAGE.value == "knowledge_package"


def test_domain_memory_selection_decision_code_enum() -> None:
    assert DomainMemorySelectionDecisionCode.SELECTED.value == "selected"
    assert (
        DomainMemorySelectionDecisionCode.EXCLUDED_DOMAIN_INAPPLICABLE.value
        == "excluded_domain_inapplicable"
    )
    assert (
        DomainMemorySelectionDecisionCode.EXCLUDED_PERMISSION_DENIED.value
        == "excluded_permission_denied"
    )


def test_domain_memory_validation_code_enum() -> None:
    assert DomainMemoryValidationCode.VALID.value == "valid"
    assert (
        DomainMemoryValidationCode.INVALID_REFERENCE_INTEGRITY.value
        == "invalid_reference_integrity"
    )


def test_domain_memory_reference_creation_and_immutability() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:health",
        applicable_domains=("domain:health", "domain:fitness"),
        sensitivity_level="RESTRICTED",
        version=1,
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
        metadata={"category": "vital_stats"},
    )

    assert ref.reference_id == "ref:knowledge:1"
    assert ref.kind == DomainMemoryReferenceKind.KNOWLEDGE_ITEM
    assert ref.canonical_id == "item:100"
    assert str(ref.domain_id) == "domain:health"
    assert ref.applicable_domains == (DomainId(slug="fitness"), DomainId(slug="health"))
    assert ref.digest is not None
    assert len(ref.digest) == 64

    with pytest.raises(AttributeError):
        ref.version = 2  # type: ignore[misc]


def test_domain_memory_reference_serialization_roundtrip() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:knowledge:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:100",
        domain_id="domain:health",
        applicable_domains=("domain:health",),
        version=1,
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
        metadata={"category": "vital_stats"},
    )
    serialized = ref.to_dict()
    deserialized = DomainMemoryReference.from_dict(serialized)
    assert deserialized == ref
    assert deserialized.to_dict() == serialized
    assert json.dumps(ref.to_dict(), allow_nan=False)


def test_domain_memory_reference_rejects_unknown_fields() -> None:
    data = {
        "reference_id": "ref:1",
        "kind": "knowledge_item",
        "canonical_id": "item:1",
        "domain_id": "domain:health",
        "unknown_extra_field": "bad",
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReference.from_dict(data)


def test_domain_memory_reference_rejects_coercion() -> None:
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReference(
            reference_id=12345,  # type: ignore[arg-type]
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:1",
            domain_id="domain:health",
        )


def test_domain_memory_reference_rejects_non_finite_floats() -> None:
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReference(
            reference_id="ref:1",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:1",
            domain_id="domain:health",
            metadata={"priority": float("nan")},
        )


def test_domain_memory_reference_mapping_proxy_privacy_bypass_rejected() -> None:
    with pytest.raises(DomainMemoryPrivacyError):
        DomainMemoryReference(
            reference_id="ref:1",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:1",
            domain_id="domain:health",
            metadata=MappingProxyType({"payload": "secret-value"}),
        )


def test_domain_memory_view_request_creation_and_serialization() -> None:
    ref = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        requested_kinds=(DomainMemoryReferenceKind.KNOWLEDGE_ITEM,),
        candidates=(ref,),
        permission_decision_ids=("perm:1",),
    )

    assert req.request_id == "req:1"
    assert req.digest is not None

    serialized = req.to_dict()
    deserialized = DomainMemoryViewRequest.from_dict(serialized)
    assert deserialized == req
    assert json.dumps(req.to_dict(), allow_nan=False)


def test_domain_memory_view_request_rejects_duplicate_candidate_reference_id() -> None:
    ref1 = DomainMemoryReference(
        reference_id="ref:dup",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
    )
    ref2 = DomainMemoryReference(
        reference_id="ref:dup",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:2",
        domain_id="domain:health",
    )
    with pytest.raises(
        DomainMemoryContractError, match="Duplicate candidate reference_id"
    ):
        DomainMemoryViewRequest(
            request_id="req:dup",
            primary_domain="domain:health",
            candidates=(ref1, ref2),
        )


def test_domain_memory_view_request_rejects_primary_domain_in_supporting_domains() -> (
    None
):
    with pytest.raises(
        DomainMemoryContractError,
        match="primary_domain cannot appear in supporting_domains",
    ):
        DomainMemoryViewRequest(
            request_id="req:1",
            primary_domain="domain:health",
            supporting_domains=("domain:health",),
        )


def test_domain_memory_view_order_independent_hashing() -> None:
    ref1 = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
    )
    ref2 = DomainMemoryReference(
        reference_id="ref:2",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:2",
        domain_id="domain:health",
    )
    dec1 = DomainMemorySelectionDecision(
        reference_id="ref:1",
        code=DomainMemorySelectionDecisionCode.SELECTED,
    )
    dec2 = DomainMemorySelectionDecision(
        reference_id="ref:2",
        code=DomainMemorySelectionDecisionCode.SELECTED,
    )

    dummy_req_digest = "0" * 64
    content_digest = _sha256_digest(
        {
            "request_id": "req:1",
            "primary_domain": "domain:health",
            "request_digest": dummy_req_digest,
            "selection_decisions": [dec1.to_dict(), dec2.to_dict()],
            "selected_references": [ref1.to_dict(), ref2.to_dict()],
        }
    )
    view_id = (
        "view:req:1:"
        f"{content_digest[:_DIGEST_PREFIX_LENGTH]}"
    )

    view1 = DomainMemoryView(
        view_id=view_id,
        request_id="req:1",
        primary_domain="domain:health",
        request_digest=dummy_req_digest,
        selection_decisions=(dec1, dec2),
        selected_references=(ref1, ref2),
    )
    view2 = DomainMemoryView(
        view_id=view_id,
        request_id="req:1",
        primary_domain="domain:health",
        request_digest=dummy_req_digest,
        selection_decisions=(dec2, dec1),
        selected_references=(ref2, ref1),
    )

    assert view1.content_digest == view2.content_digest
    assert view1.digest == view2.digest
    assert view1.to_dict() == view2.to_dict()


def test_domain_memory_validation_result_rejects_contradictory_combinations() -> None:
    with pytest.raises(
        DomainMemoryContractError, match="is_valid=True requires code=VALID"
    ):
        DomainMemoryValidationResult(
            is_valid=True,
            code=DomainMemoryValidationCode.INVALID_STRUCTURE,
            codes=(DomainMemoryValidationCode.INVALID_STRUCTURE,),
        )

    with pytest.raises(
        DomainMemoryContractError, match="is_valid=True requires codes=\\(VALID,\\)"
    ):
        DomainMemoryValidationResult(
            is_valid=True,
            code=DomainMemoryValidationCode.VALID,
            codes=(DomainMemoryValidationCode.VALID, DomainMemoryValidationCode.INVALID_STRUCTURE),
        )

    with pytest.raises(
        DomainMemoryContractError, match="is_valid=False requires non-VALID code"
    ):
        DomainMemoryValidationResult(
            is_valid=False,
            code=DomainMemoryValidationCode.VALID,
            codes=(DomainMemoryValidationCode.VALID,),
        )


def test_domain_memory_inventory_rejects_untyped_item() -> None:
    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReferenceInventory(proposals=(123,))  # type: ignore[arg-type]


def test_domain_memory_inventory_from_dict_rejects_unknown_fields() -> None:
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({"unexpected": "x"})


@pytest.mark.parametrize(
    "kinds_order",
    [
        (DomainMemoryReferenceKind.KNOWLEDGE_ITEM, DomainMemoryReferenceKind.RESOURCE),
        (DomainMemoryReferenceKind.RESOURCE, DomainMemoryReferenceKind.KNOWLEDGE_ITEM),
    ],
)
def test_domain_memory_request_permutation_determinism(kinds_order: tuple) -> None:
    ref = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
    )
    req = DomainMemoryViewRequest(
        request_id="req:1",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness", "domain:diet"),
        requested_kinds=kinds_order,
        candidates=(ref,),
        permission_decision_ids=("perm:2", "perm:1"),
    )
    assert req.supporting_domains == (DomainId(slug="diet"), DomainId(slug="fitness"))
    assert req.permission_decision_ids == ("perm:1", "perm:2")
    assert req.requested_kinds == (
        DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        DomainMemoryReferenceKind.RESOURCE,
    )


def _make_empty_content_bound_view() -> DomainMemoryView:
    dummy_req_digest = "0" * 64
    content_digest = _sha256_digest(
        {
            "request_id": "req:identity",
            "primary_domain": "domain:health",
            "request_digest": dummy_req_digest,
            "selection_decisions": [],
            "selected_references": [],
        }
    )
    return DomainMemoryView(
        view_id=(
            "view:req:identity:"
            f"{content_digest[:_DIGEST_PREFIX_LENGTH]}"
        ),
        request_id="req:identity",
        primary_domain="domain:health",
        request_digest=dummy_req_digest,
    )


def test_view_constructor_rejects_tampered_content_bound_id() -> None:
    valid = _make_empty_content_bound_view()

    with pytest.raises(
        DomainMemoryContractError,
        match="view_id suffix must match content_digest prefix",
    ):
        DomainMemoryView(
            view_id="view:req:identity:deadbeefdead",
            request_id=valid.request_id,
            primary_domain=valid.primary_domain,
            request_digest=valid.request_digest,
            selection_decisions=valid.selection_decisions,
            selected_references=valid.selected_references,
        )


def test_view_from_dict_rejects_tampered_content_bound_id() -> None:
    payload = _make_empty_content_bound_view().to_dict()
    payload["view_id"] = "view:req:identity:deadbeefdead"

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict(payload)


@pytest.mark.parametrize(
    "bad_digest",
    (
        "abc123def456",
        "g" * 64,
        "0" * 63,
        "0" * 65,
    ),
)
def test_view_snapshot_requires_full_sha256_digest(
    bad_digest: str,
) -> None:
    with pytest.raises(
        DomainMemoryContractError,
        match="view_digest must be a full SHA-256 hex digest",
    ):
        DomainMemoryViewSnapshot(
            view_id="view:req:identity:abc123def456",
            request_id="req:identity",
            primary_domain="domain:health",
            view_digest=bad_digest,
        )


def test_view_snapshot_id_suffix_must_match_digest() -> None:
    view_digest = "a" * 64

    with pytest.raises(
        DomainMemoryContractError,
        match="view_id suffix must match view_digest prefix",
    ):
        DomainMemoryViewSnapshot(
            view_id="view:req:identity:deadbeefdead",
            request_id="req:identity",
            primary_domain="domain:health",
            view_digest=view_digest,
        )


@pytest.mark.parametrize("invalidated", (0, "", None))
def test_temporal_snapshot_requires_exact_boolean_invalidated(
    invalidated: object,
) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(
        DomainMemoryContractError,
        match="invalidated must be a boolean",
    ):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            invalidated=invalidated,  # type: ignore[arg-type]
        )


def test_reference_rejects_lowercase_sensitivity_level() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryReference,
        DomainMemoryReferenceKind,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReference(
            reference_id="ref:strict:sensitivity",
            kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
            canonical_id="item:strict:sensitivity",
            domain_id="domain:health",
            sensitivity_level="secret",
        )


def test_permission_rejects_lowercase_capability() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryPermissionDecisionSnapshot(
            decision_id="perm:strict:capability",
            allowed=True,
            capabilities=("read",),
            target_domain_id="domain:health",
        )


def test_proposal_rejects_uppercase_noncanonical_kind() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryProposalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(
            proposal_id="prop:strict:kind",
            proposal_kind="MEMORY_UPDATE",
            affected_reference_ids=("ref:strict:kind",),
            required_capabilities=("PROPOSE",),
        )


def test_temporal_rejects_uppercase_noncanonical_kind() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind="INTERVAL",
            valid_from="2026-01-01T00:00:00+00:00",
            valid_to="2026-12-31T23:59:59+00:00",
        )


def test_permission_rejects_lowercase_sensitivity_level() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryPermissionDecisionSnapshot(
            decision_id="perm:strict:sensitivity",
            allowed=True,
            capabilities=("READ",),
            sensitivity_levels=("secret",),
            target_domain_id="domain:health",
        )


def test_proposal_rejects_lowercase_required_capability() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryProposalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(
            proposal_id="prop:strict:capability",
            proposal_kind="memory_update",
            affected_reference_ids=("ref:strict:capability",),
            required_capabilities=("propose",),
        )


@pytest.mark.parametrize("bad_domain", (0, False, ""))
def test_permission_from_dict_rejects_invalid_source_domain(bad_domain: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemorySerializationError,
    )

    payload = {
        "decision_id": "perm:1",
        "allowed": True,
        "capabilities": ["READ"],
        "target_domain_id": "domain:health",
        "source_domain_id": bad_domain,
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryPermissionDecisionSnapshot.from_dict(payload)


@pytest.mark.parametrize("bad_domain", (0, False, ""))
def test_permission_from_dict_rejects_invalid_target_domain(bad_domain: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemorySerializationError,
    )

    payload = {
        "decision_id": "perm:1",
        "allowed": True,
        "capabilities": ["READ"],
        "target_domain_id": bad_domain,
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryPermissionDecisionSnapshot.from_dict(payload)


@pytest.mark.parametrize("bad_reason", (1, True, [1, 2], {"a": 1}))
def test_temporal_constructor_rejects_non_string_invalidation_reason(bad_reason: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            invalidated=True,
            invalidation_reason=bad_reason,
        )


def test_temporal_constructor_rejects_free_text_invalidation_reason() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            invalidated=True,
            invalidation_reason="free text narrative reason with spaces",
        )


@pytest.mark.parametrize("bad_superseded", (1, True, "free text narrative with spaces"))
def test_temporal_constructor_rejects_invalid_superseded_by(bad_superseded: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            superseded_by=bad_superseded,
        )


@pytest.mark.parametrize("bad_collections", (0, False, 123, "not_a_list"))
def test_view_from_dict_rejects_non_sequence_selection_decisions(bad_collections: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySerializationError,
        DomainMemoryView,
    )

    payload = {
        "view_id": "view:req:1:889603298305",
        "request_id": "req:1",
        "primary_domain": "domain:health",
        "request_digest": "0" * 64,
        "selection_decisions": bad_collections,
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict(payload)


@pytest.mark.parametrize(
    "bad_digest",
    (
        None,
        "",
        "0" * 63,
        "0" * 65,
        "A" * 64,
        "g" * 64,
        123,
    ),
)
def test_view_constructor_rejects_invalid_request_digest(bad_digest: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryView,
    )

    with pytest.raises((DomainMemoryContractError, TypeError)):
        DomainMemoryView(
            view_id="view:req:1:889603298305",
            request_id="req:1",
            primary_domain="domain:health",
            request_digest=bad_digest,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "bad_digest",
    (
        None,
        "",
        "0" * 63,
        "0" * 65,
        "A" * 64,
        "g" * 64,
        123,
    ),
)
def test_view_from_dict_rejects_invalid_request_digest(bad_digest: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySerializationError,
        DomainMemoryView,
    )

    payload = {
        "view_id": "view:req:1:889603298305",
        "request_id": "req:1",
        "primary_domain": "domain:health",
        "request_digest": bad_digest,
        "selection_decisions": [],
        "selected_references": [],
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict(payload)


def test_view_from_dict_rejects_missing_request_digest() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySerializationError,
        DomainMemoryView,
    )

    payload = {
        "view_id": "view:req:1:889603298305",
        "request_id": "req:1",
        "primary_domain": "domain:health",
        "selection_decisions": [],
        "selected_references": [],
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict(payload)


@pytest.mark.parametrize("bad_val", ("", b"", {}, False, 0, 1))
def test_no_implicit_coercion_for_collections_from_dict(bad_val: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryProposalSnapshot,
        DomainMemoryReferenceInventory,
        DomainMemorySerializationError,
        DomainMemoryViewRequest,
    )

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryViewRequest.from_dict({
            "request_id": "req:1",
            "primary_domain": "domain:health",
            "supporting_domains": bad_val,
        })

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryViewRequest.from_dict({
            "request_id": "req:1",
            "primary_domain": "domain:health",
            "permission_decision_ids": bad_val,
        })

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryPermissionDecisionSnapshot.from_dict({
            "decision_id": "perm:1",
            "allowed": True,
            "capabilities": bad_val,
        })

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({
            "references": bad_val,
        })

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryProposalSnapshot.from_dict({
            "proposal_id": "prop:1",
            "proposal_kind": "memory_update",
            "affected_reference_ids": bad_val,
            "required_capabilities": ["propose"],
        })


@pytest.mark.parametrize("bad_val", ("", b"", {}, False, 0, 1, ["list_instead_of_tuple"]))
def test_no_implicit_coercion_for_collections_direct_constructor(bad_val: Any) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryProposalSnapshot,
        DomainMemoryViewRequest,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryViewRequest(
            request_id="req:1",
            primary_domain="domain:health",
            supporting_domains=bad_val,
        )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryPermissionDecisionSnapshot(
            decision_id="perm:1",
            allowed=True,
            capabilities=bad_val,
        )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(
            proposal_id="prop:1",
            proposal_kind="memory_update",
            affected_reference_ids=bad_val,
            required_capabilities=("propose",),
        )


@pytest.mark.parametrize(
    "bad_reason",
    (
        "free_text_narrative_reason",
        "freeTextNarrativeReason",
        "free_text_narrative",
        "freeTextNarrative",
    ),
)
def test_temporal_constructor_rejects_narrative_invalidation_reason(bad_reason: str) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            invalidated=True,
            invalidation_reason=bad_reason,
        )


@pytest.mark.parametrize(
    "bad_superseded",
    (
        "free_text_narrative_reason",
        "freeTextNarrativeReason",
        "free_text_narrative",
        "freeTextNarrative",
    ),
)
def test_temporal_constructor_rejects_narrative_superseded_by(bad_superseded: str) -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryTemporalSnapshot(
            kind=DomainMemoryTemporalKind.TIMELESS,
            superseded_by=bad_superseded,
        )


def test_direct_construction_with_none_raises_contract_error() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryContractError,
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryProposalBinding,
        DomainMemoryProposalSnapshot,
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemorySelectionDecision,
        DomainMemoryValidationResult,
        DomainMemoryView,
        DomainMemoryViewRequest,
    )

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryViewRequest(request_id="req:1", primary_domain="domain:health", supporting_domains=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryPermissionDecisionSnapshot(decision_id="perm:1", allowed=True, capabilities=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalSnapshot(proposal_id="prop:1", proposal_kind="memory_update", affected_reference_ids=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReference(reference_id="ref:1", canonical_id="item:1", domain_id="domain:health", kind="knowledge_item", evidence_ids=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemorySelectionDecision(reference_id="ref:1", code="selected", related_reference_ids=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryProposalBinding(binding_id="binding:domain:health:trace:1:view:req:1:abc:123", domain_id="domain:health", trace_id="trace:1", view_id="view:req:1:abc", memory_proposal_ids=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryReferenceInventory(references=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryValidationResult(is_valid=True, code="valid", codes=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryView(view_id="view:1", request_id="req:1", primary_domain="domain:health", request_digest="a" * 64, selection_decisions=None)

    with pytest.raises(DomainMemoryContractError):
        DomainMemoryView(view_id="view:1", request_id="req:1", primary_domain="domain:health", request_digest="a" * 64, selected_references=None)


def test_from_dict_with_null_collection_raises_serialization_error() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryPermissionDecisionSnapshot,
        DomainMemoryProposalSnapshot,
        DomainMemoryReferenceInventory,
        DomainMemorySelectionDecision,
        DomainMemorySerializationError,
        DomainMemoryValidationResult,
        DomainMemoryView,
        DomainMemoryViewRequest,
    )

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryViewRequest.from_dict({"request_id": "req:1", "primary_domain": "domain:health", "supporting_domains": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryViewRequest.from_dict({"request_id": "req:1", "primary_domain": "domain:health", "permission_decision_ids": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryPermissionDecisionSnapshot.from_dict({"decision_id": "perm:1", "allowed": True, "capabilities": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({"references": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemorySelectionDecision.from_dict({"reference_id": "ref:1", "code": "selected", "related_reference_ids": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryValidationResult.from_dict({"is_valid": True, "code": "valid", "codes": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryProposalSnapshot.from_dict({"proposal_id": "prop:1", "proposal_kind": "memory_update", "affected_reference_ids": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryValidationResult.from_dict({"is_valid": True, "code": "valid", "affected_object_ids": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict({"view_id": "view:1", "request_id": "req:1", "primary_domain": "domain:health", "request_digest": "a" * 64, "selection_decisions": None})

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict({"view_id": "view:1", "request_id": "req:1", "primary_domain": "domain:health", "request_digest": "a" * 64, "selected_references": None})


def test_from_dict_rejects_non_list_and_subclass_collections() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemorySerializationError,
        DomainMemoryView,
    )

    class CustomList(list):
        pass

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict({
            "view_id": "view:1",
            "request_id": "req:1",
            "primary_domain": "domain:health",
            "request_digest": "a" * 64,
            "selection_decisions": (),
            "selected_references": [],
        })

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryView.from_dict({
            "view_id": "view:1",
            "request_id": "req:1",
            "primary_domain": "domain:health",
            "request_digest": "a" * 64,
            "selection_decisions": [],
            "selected_references": CustomList(),
        })


def test_from_dict_rejects_preconstructed_snapshot_instances() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySerializationError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    temp_snap = DomainMemoryTemporalSnapshot(kind=DomainMemoryTemporalKind.TIMELESS)
    ref = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )

    ref_dict = ref.to_dict()
    ref_dict["temporal"] = temp_snap
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReference.from_dict(ref_dict)

    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({
            "references": [ref],
        })


def test_from_dict_rejects_dict_subclass_for_nested_objects() -> None:
    from cmm.domains.memory_contracts import (
        DomainMemoryReference,
        DomainMemoryReferenceInventory,
        DomainMemoryReferenceKind,
        DomainMemorySerializationError,
        DomainMemoryTemporalKind,
        DomainMemoryTemporalSnapshot,
    )

    class DictSubclass(dict):
        pass

    temp_snap = DomainMemoryTemporalSnapshot(kind=DomainMemoryTemporalKind.TIMELESS)
    ref = DomainMemoryReference(
        reference_id="ref:1",
        kind=DomainMemoryReferenceKind.KNOWLEDGE_ITEM,
        canonical_id="item:1",
        domain_id="domain:health",
        evidence_ids=("ev:1",),
        resource_ids=("res:1",),
    )

    # 1. DomainMemoryReference.from_dict with temporal as DictSubclass
    ref_dict = ref.to_dict()
    ref_dict["temporal"] = DictSubclass(temp_snap.to_dict())
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReference.from_dict(ref_dict)

    # Positive control: exact dict is accepted
    ref_dict["temporal"] = temp_snap.to_dict()
    parsed_ref = DomainMemoryReference.from_dict(ref_dict)
    assert parsed_ref.temporal == temp_snap

    # 2. DomainMemoryReferenceInventory.from_dict with reference as DictSubclass
    ref_json = ref.to_dict()
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({
            "references": [DictSubclass(ref_json)],
        })

    # 3. DomainMemoryReferenceInventory.from_dict with proposal as DictSubclass
    prop_json = {
        "proposal_id": "prop:1",
        "proposal_kind": "memory_update",
        "affected_reference_ids": ["ref:1"],
        "required_capabilities": ["PROPOSE"],
    }
    with pytest.raises(DomainMemorySerializationError):
        DomainMemoryReferenceInventory.from_dict({
            "proposals": [DictSubclass(prop_json)],
        })

    # Positive control: exact dict in inventory is accepted
    inv = DomainMemoryReferenceInventory.from_dict({
        "references": [ref_json],
        "proposals": [prop_json],
    })
    assert len(inv.references) == 1
    assert len(inv.proposals) == 1
