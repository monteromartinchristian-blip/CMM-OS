"""Tests for Phase 10.45 Domain Interface Integration contracts."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.errors import (
    DomainInterfaceContractError,
    DomainInterfaceSerializationError,
)
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    CrossDomainInterfaceView,
    DomainCenterDomainView,
    DomainCenterView,
    DomainInterfaceIntent,
    DomainInterfaceIntentKind,
    DomainInterfaceIntentResult,
    DomainInterfaceProjection,
    DomainInterfaceProjectionRequest,
    DomainInterfaceReference,
    DomainInterfaceStatus,
    DomainInterfaceViewKind,
    DomainReviewCenterView,
    DomainReviewItemView,
    DomainSelectorView,
)


def _conversational_view(**overrides: object) -> ConversationalDomainView:
    values: dict[str, object] = {
        "primary_domain": "domain:health",
        "supporting_domains": ("domain:general",),
        "workflow_refs": ("workflow:1",),
        "question_refs": (),
        "approval_refs": ("approval:1",),
        "source_refs": ("knowledge:item:1",),
        "contradiction_refs": ("contradiction:1",),
        "result_refs": ("result:1",),
        "memory_proposal_refs": ("proposal:1",),
        "confidence": 0.72,
        "warning_refs": (),
        "status": DomainInterfaceStatus.READY,
    }
    values.update(overrides)
    return ConversationalDomainView(**values)


def _projection_request(**overrides: object) -> DomainInterfaceProjectionRequest:
    values: dict[str, object] = {
        "request_id": "interface-request:1",
        "resolution_reference_id": "resolution:1",
        "composition_reference_id": "composition:1",
        "session_reference_id": "session:1",
        "requested_views": (
            DomainInterfaceViewKind.CONVERSATIONAL,
            DomainInterfaceViewKind.SELECTOR,
            DomainInterfaceViewKind.DOMAIN_CENTER,
            DomainInterfaceViewKind.CROSS_DOMAIN,
            DomainInterfaceViewKind.REVIEW_CENTER,
        ),
    }
    values.update(overrides)
    return DomainInterfaceProjectionRequest(**values)


def _sample_projection(**overrides: object) -> DomainInterfaceProjection:
    values: dict[str, object] = {
        "projection_id": "interface-projection:1",
        "request_id": "interface-request:1",
        "resolution_reference_id": "resolution:1",
        "composition_reference_id": "composition:1",
        "session_reference_id": "session:1",
        "conversational": _conversational_view(),
        "selector": DomainSelectorView(
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            rejected_domains=(),
            ambiguous_domains=(),
            reason_refs=("resolution-reason:1",),
            requires_clarification=False,
            status=DomainInterfaceStatus.READY,
        ),
        "domain_center": DomainCenterView(
            domains=(
                DomainCenterDomainView(
                    domain_id="domain:general",
                    status="active",
                    enabled=True,
                    version="1.0.0",
                    capability_refs=(),
                    permission_refs=(),
                    operation_refs=(),
                    workflow_refs=(),
                    metric_refs=(),
                    error_refs=(),
                    update_status="unknown",
                ),
            )
        ),
        "cross_domain": CrossDomainInterfaceView(
            primary_domain="domain:health",
            supporting_domains=("domain:general",),
            transfer_refs=(),
            dependency_refs=(),
            conflict_refs=(),
            consolidated_result_ref="cross-domain-result:1",
            status=DomainInterfaceStatus.READY,
        ),
        "review_center": DomainReviewCenterView(
            items=(
                DomainReviewItemView(
                    review_ref="approval:1",
                    category="operation_approval",
                    state="pending",
                    domain_id="domain:health",
                    operation_ref="health.prepare_medical_appointment",
                    workflow_ref=None,
                    session_ref="session:1",
                    reason_ref="approval_required",
                ),
            )
        ),
        "content_digest": "",
    }
    values.update(overrides)
    return DomainInterfaceProjection(**values)


class TestEnums:
    def test_interface_view_kind_values_are_closed(self) -> None:
        assert [item.value for item in DomainInterfaceViewKind] == [
            "conversational",
            "selector",
            "domain_center",
            "cross_domain",
            "review_center",
        ]

    def test_interface_intent_kind_values_are_closed(self) -> None:
        assert [item.value for item in DomainInterfaceIntentKind] == [
            "select_primary",
            "auto_resolve",
            "add_supporting",
            "withdraw_supporting",
            "explain_selection",
            "request_policy_change",
        ]

    def test_interface_status_values_are_closed(self) -> None:
        assert [item.value for item in DomainInterfaceStatus] == [
            "ready",
            "partial",
            "blocked",
            "degraded",
            "unavailable",
            "pending",
        ]


class TestImmutability:
    def test_projection_contracts_are_frozen_and_tuple_based(self) -> None:
        view = _conversational_view()

        assert view.primary_domain == "domain:health"
        assert view.supporting_domains == ("domain:general",)
        assert view.confidence == 0.72
        with pytest.raises(FrozenInstanceError):
            view.primary_domain = "domain:general"  # type: ignore[misc]

    def test_contracts_are_slotted(self) -> None:
        for contract in (
            ConversationalDomainView,
            DomainSelectorView,
            DomainCenterDomainView,
            DomainCenterView,
            CrossDomainInterfaceView,
            DomainReviewItemView,
            DomainReviewCenterView,
            DomainInterfaceProjectionRequest,
            DomainInterfaceProjection,
            DomainInterfaceIntent,
            DomainInterfaceIntentResult,
            DomainInterfaceReference,
        ):
            assert "__slots__" in contract.__dict__, contract.__name__

    def test_projection_is_immutable(self) -> None:
        projection = _sample_projection()
        with pytest.raises(FrozenInstanceError):
            projection.conversational = None  # type: ignore[misc]


class TestReferenceNormalization:
    def test_duplicate_references_are_deduplicated_in_canonical_order(self) -> None:
        view = _conversational_view(
            supporting_domains=(
                "domain:general",
                "domain:general",
                "domain:legal",
                "domain:legal",
            )
        )
        assert view.supporting_domains == ("domain:general", "domain:legal")

    def test_mutable_list_inputs_are_normalized_to_tuples(self) -> None:
        view = _conversational_view(
            supporting_domains=["domain:general", "domain:legal"],
            approval_refs=["approval:1"],
        )
        assert view.supporting_domains == ("domain:general", "domain:legal")
        assert isinstance(view.supporting_domains, tuple)
        assert view.approval_refs == ("approval:1",)

    def test_blank_references_are_rejected(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _conversational_view(workflow_refs=(" ",))
        with pytest.raises(DomainInterfaceContractError):
            _conversational_view(supporting_domains=("",))

    def test_primary_domain_must_be_non_blank(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _conversational_view(primary_domain="")

    def test_empty_reference_tuple_is_valid(self) -> None:
        view = _conversational_view(supporting_domains=())
        assert view.supporting_domains == ()


class TestConfidenceValidation:
    @pytest.mark.parametrize(
        "confidence",
        [-0.01, 1.01, math.nan, math.inf, -math.inf, True],
    )
    def test_invalid_confidence_is_rejected(self, confidence: object) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _conversational_view(confidence=confidence)

    @pytest.mark.parametrize("confidence", [0.0, 1.0, 0.72, None])
    def test_valid_confidence_is_accepted(self, confidence: float | None) -> None:
        view = _conversational_view(confidence=confidence)
        assert view.confidence == confidence


class TestRequestedViews:
    def test_invalid_view_kind_is_rejected(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _projection_request(requested_views=("dashboard",))

    def test_view_kind_strings_are_coerced(self) -> None:
        request = _projection_request(
            requested_views=("domain_center", "conversational")
        )
        assert request.requested_views == (
            DomainInterfaceViewKind.DOMAIN_CENTER,
            DomainInterfaceViewKind.CONVERSATIONAL,
        )

    def test_empty_requested_views_are_rejected(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _projection_request(requested_views=())

    def test_duplicate_requested_views_are_deduplicated(self) -> None:
        request = _projection_request(
            requested_views=("conversational", "conversational", "selector")
        )
        assert request.requested_views == (
            DomainInterfaceViewKind.CONVERSATIONAL,
            DomainInterfaceViewKind.SELECTOR,
        )


class TestDomainCenter:
    def test_domain_center_sorts_domains_by_canonical_id(self) -> None:
        view = DomainCenterView(
            domains=(
                DomainCenterDomainView(
                    domain_id="domain:health",
                    status="active",
                    enabled=True,
                    version="1.0.0",
                ),
                DomainCenterDomainView(
                    domain_id="domain:general",
                    status="disabled",
                    enabled=False,
                    version="2.1.0",
                ),
            )
        )
        assert [item.domain_id for item in view.domains] == [
            "domain:general",
            "domain:health",
        ]

    def test_domain_center_rejects_non_blank_domain_state(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            DomainCenterDomainView(
                domain_id="domain:health",
                status="",
                enabled=True,
                version="1.0.0",
            )


class TestReferenceContract:
    def test_domain_interface_reference_validates_identity(self) -> None:
        reference = DomainInterfaceReference(
            reference_id="approval:1", category="approval"
        )
        assert reference.reference_id == "approval:1"
        assert reference.category == "approval"
        assert reference.domain_id is None

    def test_domain_interface_reference_rejects_blank_values(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            DomainInterfaceReference(reference_id="", category="approval")
        with pytest.raises(DomainInterfaceContractError):
            DomainInterfaceReference(reference_id="approval:1", category=" ")


class TestSerialization:
    def test_view_serialization_is_deterministic(self) -> None:
        view = _conversational_view()
        assert view.to_dict() == view.to_dict()
        assert view.to_dict()["primary_domain"] == "domain:health"
        assert view.to_dict()["supporting_domains"] == ["domain:general"]
        assert view.to_dict()["status"] == "ready"
        assert view.to_dict()["confidence"] == 0.72

    def test_projection_serialization_round_trip(self) -> None:
        projection = _sample_projection()
        payload = projection.to_dict()
        assert payload["resolution_reference_id"] == "resolution:1"
        assert payload["composition_reference_id"] == "composition:1"
        restored = DomainInterfaceProjection.from_dict(payload)
        assert restored == projection

    def test_all_contracts_round_trip_through_serialization(self) -> None:
        contracts = (
            _conversational_view(),
            DomainSelectorView(
                primary_domain="domain:health",
                supporting_domains=(),
                rejected_domains=(),
                ambiguous_domains=(),
                reason_refs=(),
                requires_clarification=False,
                status=DomainInterfaceStatus.READY,
            ),
            DomainCenterDomainView(
                domain_id="domain:health",
                status="active",
                enabled=True,
                version="1.0.0",
            ),
            DomainCenterView(domains=()),
            CrossDomainInterfaceView(
                primary_domain="domain:health",
                supporting_domains=(),
                transfer_refs=(),
                dependency_refs=(),
                conflict_refs=(),
                consolidated_result_ref=None,
                status=DomainInterfaceStatus.PARTIAL,
            ),
            DomainReviewItemView(
                review_ref="approval:1",
                category="operation_approval",
                state="pending",
            ),
            DomainReviewCenterView(items=()),
            _projection_request(),
            DomainInterfaceIntent(
                intent_id="intent:1",
                kind=DomainInterfaceIntentKind.AUTO_RESOLVE,
                resolution_reference_id="resolution:1",
                composition_reference_id="composition:1",
            ),
            DomainInterfaceIntentResult(
                intent_id="intent:1",
                accepted=True,
                status=DomainInterfaceStatus.READY,
                resolution_reference_id="resolution:1",
                composition_reference_id="composition:1",
                reason_code="accepted",
            ),
        )
        for contract in contracts:
            restored = type(contract).from_dict(contract.to_dict())
            assert restored == contract, type(contract).__name__

    def test_from_dict_rejects_missing_required_field(self) -> None:
        payload = _conversational_view().to_dict()
        del payload["primary_domain"]
        with pytest.raises(DomainInterfaceSerializationError):
            ConversationalDomainView.from_dict(payload)

    def test_from_dict_rejects_invalid_enum_value(self) -> None:
        payload = _conversational_view().to_dict()
        payload["status"] = "not-a-status"
        with pytest.raises(DomainInterfaceSerializationError):
            ConversationalDomainView.from_dict(payload)


class TestProjectionDigest:
    def test_projection_digest_is_hex64_and_deterministic(self) -> None:
        first = _sample_projection()
        second = _sample_projection()
        assert len(first.content_digest) == 64
        assert first.content_digest == first.content_digest.lower()
        assert first.content_digest == second.content_digest

    def test_projection_digest_binds_canonical_content(self) -> None:
        base = _sample_projection()
        changed = _sample_projection(
            conversational=_conversational_view(confidence=0.5)
        )
        assert changed.content_digest != base.content_digest

    def test_projection_rejects_incoherent_digest(self) -> None:
        with pytest.raises(DomainInterfaceContractError):
            _sample_projection(content_digest="0" * 64)
